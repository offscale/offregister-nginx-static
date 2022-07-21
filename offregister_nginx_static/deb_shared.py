from os import path

from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.misc import upload_template_fmt
from offregister_fab_utils.ubuntu.systemd import restart_systemd
from pkg_resources import resource_filename


def setup_conf0(
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
        kwargs["SSL_CERTIFICATE"] = "{root}/fullchain.pem".format(root=root)
        kwargs["SSL_CERTIFICATE_KEY"] = "{root}/privkey.pem".format(root=root)

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

    conf_local_filepath = kwargs.get(
        "nginx-conf-file",
        resource_filename("offregister_nginx_static", path.join("conf", nginx_conf)),
    )
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

    top_fname = "{}/{}".format(base_conf_path, nginx_conf.replace(".conf", ".top.conf"))
    if path.isfile(top_fname):
        with open(top_fname, "rt") as f:
            kwargs["EXTRA_HEAD"] = f.read()
    else:
        kwargs.setdefault("EXTRA_HEAD", "")

    conf_name = nginx_conf.replace(".conf", ".location.conf")
    location_fname = "{}/{}".format(base_conf_path, conf_name)
    if path.isfile(location_fname):
        with open(location_fname, "rt") as f:
            location_block = f.read() % {
                k: kwargs[k] for k in builtin_contexts[conf_name]
            }
    else:
        location_block = ""

    if http_to_https and https:
        fname = "{}/{}".format(base_conf_path, nginx_conf)
        kwargs["SERVER_BODY"] = ""
        if path.isfile(fname):
            with open(fname, "rt") as f:
                nginx_config_content = f.read() % {
                    k: kwargs[k] for k in builtin_contexts[fname]
                }
        else:
            nginx_config_content = ""

        del kwargs["EXTRA_BODY_FOOT"]

        kwargs.update(
            {"EXTRA_HEAD": nginx_config_content, "SERVER_BODY": location_block}
        )
        nginx_conf = nginx_conf.replace(".conf", ".https.conf")
    else:
        kwargs["SERVER_BODY"] = location_block
    # </WEBSOCKET only (so far)>

    upload_template_fmt(
        c,
        conf_local_filepath,
        conf_remote_filename,
        context=conf_keys if conf_keys is None else {k: kwargs[k] for k in conf_keys},
        use_sudo=True,
        backup=False,
    )

    if skip_nginx_restart:
        return

    restart_systemd(c, "nginx")

    return c.sudo("systemctl status nginx --no-pager --full")


__all__ = ["setup_conf0"]
