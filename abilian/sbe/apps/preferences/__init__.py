# coding=utf-8
"""
"""
from __future__ import absolute_import

import jinja2
from abilian.services.preferences import preferences

from .panels.sbe_notifications import SbeNotificationsPanel


def register_plugin(app):
    app.register_jinja_loaders(jinja2.PackageLoader(__name__, 'templates'))
    preferences.register_panel(SbeNotificationsPanel(), app)
