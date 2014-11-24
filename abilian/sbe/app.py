"""
Static configuration for the application.

Everything is hardwired at this point. A plugin system will have to be
developped later.
"""

from time import time
import logging

import sqlalchemy as sa

import jinja2
from flask import request_started, request_tearing_down
from flask.globals import g, request
from flask.ext.login import current_user

from abilian.app import Application as BaseApplication
from abilian.core.extensions import db
from abilian.services import converter

from .apps.documents.repository import repository
from .extension import sbe

# Used for side effects, do not remove
import abilian.web.forms


__all__ = ['create_app', 'db']

logger = logging.getLogger(__name__)

def create_app(config=None):
  return Application(config=config)


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
  )

  def __init__(self, name='abilian.sbe', config=None, **kwargs):
    BaseApplication.__init__(self, name, config=config,
                             instance_relative_config=True, **kwargs)

    self.register_jinja_loaders(jinja2.PackageLoader('abilian.sbe', 'templates'))

  def init_extensions(self):
    BaseApplication.init_extensions(self)
    sbe.init_app(self)
    repository.init_app(self)
    converter.init_app(self)
