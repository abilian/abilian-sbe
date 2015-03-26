# coding=utf-8
"""
Static configuration for the application.

TODO: add more (runtime) flexibility in plugin discovery, selection
and activation.
"""
from __future__ import absolute_import

import logging

import jinja2
from flask.ext.script import Manager

from abilian.app import Application as BaseApplication
from abilian.core.extensions import db
from abilian.core.commands import setup_abilian_commands
from abilian.services import converter
from abilian.core.celery import (
  FlaskLoader as CeleryBaseLoader, FlaskCelery as BaseCelery
)
from .apps.documents.repository import repository
from .extension import sbe

# Used for side effects, do not remove
import abilian.web.forms  # noqa


__all__ = ['create_app', 'db']

logger = logging.getLogger(__name__)

def create_app(config=None):
  return Application(config=config)

# loader to be used by celery workers
class CeleryLoader(CeleryBaseLoader):
  flask_app_factory = 'abilian.sbe.app.create_app'


celery = BaseCelery(loader=CeleryLoader)


class Application(BaseApplication):

  APP_PLUGINS = (
    'abilian.web.search',
    "abilian.sbe.apps.main",
    "abilian.sbe.apps.notifications",
    "abilian.sbe.apps.preferences",
    "abilian.sbe.apps.wiki",
    "abilian.sbe.apps.wall",
    "abilian.sbe.apps.documents",
    "abilian.sbe.apps.forum",
    "abilian.sbe.apps.communities",
    "abilian.sbe.apps.social",
    "abilian.sbe.apps.preferences",
  )

  script_manager = '.app.command_manager'

  def __init__(self, name='abilian.sbe', config=None, **kwargs):
    BaseApplication.__init__(self, name, config=config, **kwargs)
    self.register_jinja_loaders(
      jinja2.PackageLoader('abilian.sbe', 'templates')
    )

  def init_extensions(self):
    BaseApplication.init_extensions(self)
    sbe.init_app(self)
    repository.init_app(self)
    converter.init_app(self)


command_manager = Manager(create_app)
setup_abilian_commands(command_manager)


def command_entry_point():
  command_manager.run()


if __name__ == '__main__':
  command_entry_point()
