# coding=utf-8
""" Communities module
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe

def register_plugin(app):
  sbe.init_app(app)
  from . import events # Used just for side effect
  from .views import communities
  from . import search
  app.register_blueprint(communities)
  search.init_app(app)
