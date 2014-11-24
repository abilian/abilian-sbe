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
  #from .webdav.views import webdav
  #from .cmis.atompub import atompub

  app.register_blueprint(documents)
  setup_listener()
  #app.register_blueprint(webdav)
  #app.register_blueprint(atompub)
