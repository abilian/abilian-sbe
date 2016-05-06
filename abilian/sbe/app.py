# coding=utf-8
"""
Static configuration for the application.

TODO: add more (runtime) flexibility in plugin discovery, selection
and activation.
"""
from __future__ import absolute_import

import logging
import os
import subprocess
import sys

import jinja2
from flask import current_app
from flask_script import Command, Manager
from pathlib import Path
from werkzeug.serving import BaseWSGIServer

from abilian.app import Application as BaseApplication
from abilian.core.celery import FlaskCelery as BaseCelery
from abilian.core.celery import FlaskLoader as CeleryBaseLoader
from abilian.core.commands import setup_abilian_commands
from abilian.core.extensions import db
from abilian.services import converter

from .apps.documents.repository import repository
from .extension import sbe

# Used for side effects, do not remove

__all__ = ['create_app', 'db']

logger = logging.getLogger(__name__)


def create_app(config=None):
    return Application(config=config)


command_manager = Manager(create_app)
setup_abilian_commands(command_manager)


# loader to be used by celery workers
class CeleryLoader(CeleryBaseLoader):
    flask_app_factory = 'abilian.sbe.app.create_app'


celery = BaseCelery(loader=CeleryLoader)


class Application(BaseApplication):

    APP_PLUGINS = BaseApplication.APP_PLUGINS + (
        "abilian.sbe.apps.main",
        "abilian.sbe.apps.notifications",
        "abilian.sbe.apps.preferences",
        "abilian.sbe.apps.wiki",
        "abilian.sbe.apps.wall",
        "abilian.sbe.apps.documents",
        "abilian.sbe.apps.forum",
        "abilian.sbe.apps.communities",
        "abilian.sbe.apps.social",
        "abilian.sbe.apps.preferences",)

    script_manager = command_manager

    def __init__(self, name='abilian_sbe', config=None, **kwargs):
        BaseApplication.__init__(self, name, config=config, **kwargs)
        loader = jinja2.PackageLoader('abilian.sbe', 'templates')
        self.register_jinja_loaders(loader)

    def init_extensions(self):
        BaseApplication.init_extensions(self)
        sbe.init_app(self)
        repository.init_app(self)
        converter.init_app(self)

# SBE demo app bootstrap stuff
_SBE_DEMO_SCRIPT = u'''\
#!{BIN_DIR}/python
from __future__ import absolute_import

import sys
from abilian.sbe.app import command_entry_point

sys.exit(command_entry_point())
'''

_BASE_SERVER_ACTIVATE = BaseWSGIServer.server_activate


def _on_http_server_activate(self, *args, **kwargs):
    """
    This function is used as to monkey patch BaseWSGIServer.server_activate
    during `setup_sbe_demo`.
    """
    _BASE_SERVER_ACTIVATE(self, *args, **kwargs)
    # now we are listening to socket
    host, port = self.server_address
    if host == u'0.0.0.0':
        # chrome is not ok with 0.0.0.0
        host = u'localhost'
    url = 'http://{host}:{port}/setup'.format(host=host, port=port)

    if sys.platform == "win32":
        os.startfile(url)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, url])


# run with python -m abilian.sbe.app setup_sbe_app
def setup_sbe_app():
    """
    Basic set up SBE application. Must be run inside a virtualenv.

    Will create `abilian_sbe` script, run a local server and open browser on app's
    setup wizard.
    """
    logger = logging.getLogger('sbe_demo')
    logger.setLevel(logging.INFO)

    if 'VIRTUAL_ENV' not in os.environ:
        logger.error('Not in a virtualenv! Aborting.')
        return 1

    bin_dir = Path(sys.prefix) / u'bin'

    if not bin_dir.exists() and bin_dir.is_dir():
        logger.error('%s doesn\'t exists or is not a directory. Aborting',
                     repr(unicode(bin_dir)))
        return 1

    script_file = bin_dir / u'abilian_sbe'
    if script_file.exists():
        logger.info('%s already exists. Skipping creation.',
                    repr(unicode(script_file)))
    else:
        with script_file.open('w') as out:
            logger.info('Create script: "%s".', repr(unicode(script_file)))
            content = _SBE_DEMO_SCRIPT.format(BIN_DIR=unicode(bin_dir))
            out.write(content)
        script_file.chmod(0755)  # 0755: -rwxr-xr-x

    current_app.config['PRODUCTION'] = True
    current_app.config['DEBUG'] = False
    current_app.config['ASSETS_DEBUG'] = False
    current_app.config['SITE_NAME'] = u'Abilian SBE'
    current_app.config['MAIL_SENDER'] = u'abilian-sbe-app@example.com'

    logger.info('Prepare CSS & JS files')
    command_manager.handle('abilian_sbe', ['assets', 'build'])
    # disabled init config: only if not running setupwizard
    # command_manager.handle('abilian_sbe', ['config', 'init'])

    # patch server used to launch browser here immediately after socket opened
    BaseWSGIServer.server_activate = _on_http_server_activate
    return command_manager.handle('abilian_sbe', ['run', '--hide-config'])


def command_entry_point():
    command_manager.run(commands={'setup_sbe_app': Command(setup_sbe_app)},)


if __name__ == '__main__':
    command_entry_point()
