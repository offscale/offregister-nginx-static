from __future__ import print_function

from os import path

from fabric.contrib.files import upload_template
from fabric.operations import sudo
from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.ubuntu.systemd import restart_systemd
from pkg_resources import resource_filename


def setup_conf0(nginx_conf='api-and-static.conf', conf_keys=None, skip_nginx_restart=False, *args, **kwargs):
    apt_depends('nginx')
    kwargs.setdefault('LISTEN_PORT', 80)
    kwargs.setdefault('NAME_OF_BLOCK', 'server_block')
    kwargs.setdefault('ROUTE_BLOCK', '')
    kwargs.setdefault('LOCATION', '/')

    if conf_keys is None:
        conf_keys = {
            'api-and-static.conf': ('SERVER_NAME', 'WWWROOT', 'API_HOST', 'API_PORT', 'LISTEN_PORT'),
            'static.conf': ('SERVER_NAME', 'WWWROOT'),
            'proxy-pass.conf': ('NAME_OF_BLOCK', 'SERVER_LOCATION', 'SERVER_NAME',
                                'ROUTE_BLOCK', 'LISTEN_PORT', 'LOCATION')
        }.get(nginx_conf)

    conf_local_filepath = kwargs.get(
        'nginx-conf-file', resource_filename('offregister_nginx_static', path.join('conf', nginx_conf))
    )
    conf_remote_filename = kwargs.get('conf_remote_filename', '/etc/nginx/conf.d/{}'.format(
        kwargs.get('nginx-conf-filename', path.basename(conf_local_filepath))
    ))
    if not conf_remote_filename.endswith('.conf'):
        conf_remote_filename += '.conf'
    upload_template(conf_local_filepath, conf_remote_filename,
                    context=conf_keys if conf_keys is None else {k: kwargs[k] for k in conf_keys},
                    use_sudo=True, backup=False)

    if skip_nginx_restart:
        return

    restart_systemd('nginx')

    return sudo('systemctl status nginx --no-pager --full')
