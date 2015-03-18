# coding=utf-8
"""
Folders / Documents module
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe


def register_plugin(app):
  sbe.init_app(app)
  from .views import documents
  from .models import setup_listener
  from .commands import manager

  app.register_blueprint(documents)
  setup_listener()

  if app.script_manager:
    app.script_manager.add_command('documents', manager)
