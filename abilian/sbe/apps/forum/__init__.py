# coding=utf-8
"""
Forum module
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe


def register_plugin(app):
  sbe.init_app(app)
  from .views import forum
  from .actions import register_actions
  from .models import ThreadIndexAdapter
  from .commands import manager

  forum.record_once(register_actions)
  app.register_blueprint(forum)
  app.services['indexing'].adapters_cls.insert(0, ThreadIndexAdapter)

  if app.script_manager:
    app.script_manager.add_command('forum', manager)
