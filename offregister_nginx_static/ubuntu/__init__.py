from os import path
from pkg_resources import resource_filename

from fabric.contrib.files import upload_template
from fabric.operations import sudo

from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.ubuntu.systemd import restart_systemd


def setup_conf0(nginx_conf='api_and_static.conf', conf_keys=None, skip_nginx_restart=False, *args, **kwargs):
    apt_depends('nginx')

    if conf_keys is None:
        conf_keys = {'api_and_static.conf': ('SERVER_NAME', 'WWWROOT', 'API_HOST', 'API_PORT'),
                     'static.conf': ('SERVER_NAME', 'WWWROOT')}.get(nginx_conf)

    conf_local_filepath = kwargs.get(
        'nginx-conf-file', resource_filename('offregister_nginx_static', path.join('conf', nginx_conf))
    )
    conf_remote_filename = '/etc/nginx/conf.d/{}'.format(
        kwargs.get('nginx-conf-filename', path.basename(conf_local_filepath))
    )
    upload_template(conf_local_filepath, conf_remote_filename,
                    context=conf_keys if conf_keys is None else {k: kwargs[k] for k in conf_keys},
                    use_sudo=True)

    if skip_nginx_restart:
        return

    restart_systemd('nginx')

    return sudo('systemctl status nginx --no-pager --full')
