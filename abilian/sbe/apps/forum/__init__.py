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

  forum.record_once(register_actions)
  app.register_blueprint(forum)
  app.services['indexing'].adapters_cls.insert(0, ThreadIndexAdapter)
