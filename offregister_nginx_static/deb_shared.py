from functools import partial
from os import path
from sys import modules

from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.misc import upload_template_fmt
from offregister_fab_utils.ubuntu.systemd import restart_systemd
from patchwork.files import exists
from pkg_resources import resource_filename

conf_dir = partial(
    path.join,
    path.dirname(resource_filename(modules[__name__].__name__, "__init__.py")),
    "conf",
)


def install_nginx0(c, *args, **kwargs):
    """
    :param c: Connection
    :type c: ```fabric.connection.Connection```
    """
    if kwargs["cache"]["os_version"] == "debian":
        apt_depends(
            c,
            "curl",
            "gnupg2",
            "ca-certificates",
            "lsb-release",
            "debian-archive-keyring",
        )
        c.sudo(
            "curl https://nginx.org/keys/nginx_signing.key"
            " | gpg --dearmor"
            " | tee /usr/share/keyrings/nginx-archive-keyring.gpg",
            hide=True,
        )
        c.run(
            "gpg --dry-run --quiet --import --import-options import-show"
            " /usr/share/keyrings/nginx-archive-keyring.gpg",
            warn=True,
        )
        c.sudo(
            'echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/debian'
            ' `lsb_release -cs` nginx"'
            " | tee /etc/apt/sources.list.d/nginx.list"
        )
        c.sudo(
            'echo -e "Package: *\\nPin: origin nginx.org\\nPin: release o=nginx\\nPin-Priority: 900\\n"'
            " | tee /etc/apt/preferences.d/99nginx"
        )
    else:
        apt_depends(
            c, "curl", "gnupg2", "ca-certificates", "lsb-release", "ubuntu-keyring"
        )
        c.sudo(
            "curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor"
            " | tee /usr/share/keyrings/nginx-archive-keyring.gpg",
            hide=True,
        )
        c.run(
            "gpg --dry-run --quiet --import --import-options import-show"
            " /usr/share/keyrings/nginx-archive-keyring.gpg",
            warn=True,
        )
        c.sudo(
            'echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg]'
            ' http://nginx.org/packages/ubuntu `lsb_release -cs` nginx"'
            " | tee /etc/apt/sources.list.d/nginx.list"
        )
        c.sudo(
            'echo -e "Package: *\\nPin: origin nginx.org\\nPin: release o=nginx\\nPin-Priority: 900\n"'
            " | tee /etc/apt/preferences.d/99nginx"
        )
    c.sudo("apt-get update -qq")
    apt_depends(c, "nginx")
    return "Installed nginx"


def setup_nginx_conf1(c, *args, **kwargs):
    """
    :param c: Connection
    :type c: ```fabric.connection.Connection```
    """
    if exists(c, runner=c.sudo, path="/etc/nginx/nginx.conf"):
        if (
            c.sudo(
                "grep -qF 'sites-enabled' /etc/nginx/nginx.conf", warn=True, hide=True
            ).exited
            != 0
        ):
            c.sudo(
                "sed -i '/include \/etc\/nginx\/conf.d\/\*.conf;/a"
                "    include \/etc\/nginx\/sites-enabled\/\*.conf;' "
                "/etc/nginx/nginx.conf"
            )
    else:
        print("[setup_nginx_conf1] nonexistent")
    print("[setup_nginx_conf1] out")


def setup_custom_conf2(
    c,
    nginx_conf="api-and-static.conf",
    conf_keys=None,
    skip_nginx_restart=False,
    http_to_https=False,
    https=False,
    *args,
    **kwargs
):
    """
    Generate a new nginx config; interpolating vars within.

    :param c: Connection
    :type c: ```fabric.connection.Connection```

    :param nginx_conf: Nginx conf local filename (for interpolation)
    :type nginx_conf: ```str```

    :param conf_keys: Valid keys that can be interpolated (from kwargs)
    :type conf_keys: ```Optional[Iterable[str]]```

    :param skip_nginx_restart: Whether to skip `nginx` restart
    :type skip_nginx_restart: ```bool```

    :param http_to_https: Whether to redirect HTTP to HTTPS
    :type http_to_https: ```bool```

    :param https: Whether to enable HTTPS (defaults to LetsEncrypt)
    :type https: ```bool```
    """
    apt_depends(c, "nginx")
    kwargs.setdefault("LISTEN_PORT", 80)
    kwargs.setdefault("NAME_OF_BLOCK", "server_block")
    kwargs.setdefault("ROUTE_BLOCK", "")
    kwargs.setdefault("LOCATION", "/")
    kwargs.setdefault("API_HOST", "127.0.0.1")
    kwargs.setdefault("API_PORT", 8000)

    kwargs.setdefault(
        "EXTRA_BODY_FOOT",
        "return 302 https://$host$request_uri" if http_to_https else "",
    )
    kwargs.setdefault("LETSENCRYPT", https)
    kwargs.setdefault("SSL_DHPARAM", "/etc/ssl/certs/dhparam.pem")
    if https and kwargs["LETSENCRYPT"] and "SERVER_NAME" in kwargs:
        root = "/etc/letsencrypt/live/{SERVER_NAME}".format(
            SERVER_NAME=kwargs["SERVER_NAME"]
        )
        kwargs.update(
            {
                "SSL_CERTIFICATE": "{root}/fullchain.pem".format(root=root),
                "SSL_CERTIFICATE_KEY": "{root}/privkey.pem".format(root=root),
            }
        )

    builtin_contexts = {
        "api-and-static.conf": (
            "SERVER_NAME",
            "WWWROOT",
            "API_HOST",
            "API_PORT",
            "LISTEN_PORT",
        ),
        "static.conf": ("SERVER_NAME", "WWWROOT"),
        "proxy-pass.conf": (
            "NAME_OF_BLOCK",
            "SERVER_LOCATION",
            "SERVER_NAME",
            "ROUTE_BLOCK",
            "LISTEN_PORT",
            "LOCATION",
        ),
        "websocket.location.conf": (
            "API_HOST",
            "API_PORT",
        ),
        "websocket.conf": (
            "EXTRA_HEAD",
            "SERVER_NAME",
            "LISTEN_PORT",
            "SERVER_BODY",
            "EXTRA_BODY_FOOT",
        ),
        "websocket.https.conf": (
            "EXTRA_HEAD",
            "SERVER_NAME",
            "SSL_CERTIFICATE",
            "SSL_CERTIFICATE_KEY",
            "SSL_DHPARAM",
            "SERVER_BODY",
        ),
    }  # type: Dict[str, Iterable[str]]
    if conf_keys is None:
        conf_keys = builtin_contexts.get(nginx_conf)

    conf_local_filepath = kwargs.get("nginx-conf-file", conf_dir(nginx_conf))
    conf_remote_filepath = kwargs.get("nginx-conf-dirname", "/etc/nginx/conf.d")
    conf_remote_filename = kwargs.get(
        "conf_remote_filename",
        "{conf_remove_filepath}/{conf_remove_basename}".format(
            conf_remove_filepath=conf_remote_filepath,
            conf_remove_basename=kwargs.get(
                "nginx-conf-filename", path.basename(conf_local_filepath)
            ),
        ),
    )
    if not conf_remote_filename.endswith(".conf"):
        conf_remote_filename += ".conf"

    # <WEBSOCKET only (so far)>
    base_conf_path = path.basename(conf_remote_filename)

    top_fname = conf_dir(nginx_conf.replace(".conf", ".top.conf"))
    if path.isfile(top_fname):
        with open(top_fname, "rt") as f:
            kwargs["EXTRA_HEAD"] = f.read()
    else:
        kwargs.setdefault("EXTRA_HEAD", "")

    conf_name = nginx_conf.replace(".conf", ".location.conf")
    location_fname = conf_dir(conf_name)
    if path.isfile(location_fname):
        with open(location_fname, "rt") as f:
            kwargs["SERVER_BODY"] = f.read() % {
                k: kwargs[k] for k in builtin_contexts[conf_name]
            }
    else:
        kwargs.setdefault("SERVER_BODY", "")

    if http_to_https and https:
        fname = "{}/{}".format(base_conf_path, nginx_conf)
        if path.isfile(fname):
            with open(fname, "rt") as f:
                nginx_config_content = f.read() % {
                    k: kwargs[k] for k in builtin_contexts[nginx_conf]
                }
        else:
            nginx_config_content = ""

        del kwargs["EXTRA_BODY_FOOT"]

        kwargs["EXTRA_HEAD"] = nginx_config_content
    # </WEBSOCKET only (so far)>

    upload_template_fmt(
        c,
        conf_local_filepath,
        conf_remote_filename,
        context=conf_keys if conf_keys is None else {k: kwargs[k] for k in conf_keys},
        use_sudo=True,
        mode=0o400,
        backup=False,
    )

    if skip_nginx_restart:
        return

    restart_systemd(c, "nginx")

    res = c.sudo("systemctl status nginx --no-pager --full")
    return res.stdout if res.exited == 0 else res.stderr


__all__ = ["install_nginx0", "setup_nginx_conf1", "setup_custom_conf2"]
