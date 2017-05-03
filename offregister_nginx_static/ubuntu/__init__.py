from os import path
from pkg_resources import resource_filename

from fabric.contrib.files import upload_template
from fabric.operations import sudo

from offregister_fab_utils.apt import apt_depends


def setup_conf0(*args, **kwargs):
    apt_depends('nginx')
    conf_local_filepath = kwargs.get('nginx-conf-file',
                                     resource_filename('offregister_nginx_static', path.join('conf', 'nginx.conf')))
    conf_remote_filename = '/etc/nginx/conf.d/{}'.format(
        kwargs.get('nginx-conf-filename', path.basename(conf_local_filepath))
    )
    upload_template(conf_local_filepath, conf_remote_filename,
                    # context={'SERVER_NAME': kwargs['SERVER_NAME'], 'SERVER_LOCATION': kwargs['SERVER_LOCATION']},
                    use_sudo=True)
    if sudo('systemctl status -q nginx --no-pager --full', warn_only=True).failed:
        sudo('systemctl start -q nginx --no-pager --full')
    else:
        sudo('systemctl stop -q nginx --no-pager --full')
        sudo('systemctl start -q nginx --no-pager --full')

    return sudo('systemctl status nginx --no-pager --full')
