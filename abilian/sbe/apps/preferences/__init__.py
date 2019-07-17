# coding=utf-8
""""""
import jinja2
from abilian.services.preferences import preferences

from abilian.sbe.app import Application

from .panels.sbe_notifications import SbeNotificationsPanel


def register_plugin(app: Application) -> None:
    app.register_jinja_loaders(jinja2.PackageLoader(__name__, "templates"))
    preferences.register_panel(SbeNotificationsPanel(), app)
