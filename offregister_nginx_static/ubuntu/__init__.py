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
    *args,
    **kwargs
):
    """
    :param c: Connection
    :type c: ```fabric.connection.Connection```
    """
    apt_depends(c, "nginx")
    kwargs.setdefault("LISTEN_PORT", 80)
    kwargs.setdefault("NAME_OF_BLOCK", "server_block")
    kwargs.setdefault("ROUTE_BLOCK", "")
    kwargs.setdefault("LOCATION", "/")

    if conf_keys is None:
        conf_keys = {
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
        }.get(nginx_conf)

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
