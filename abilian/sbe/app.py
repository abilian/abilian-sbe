# coding=utf-8
"""Static configuration for the application.

TODO: add more (runtime) flexibility in plugin discovery, selection
and activation.
"""
import logging

import jinja2
from abilian.app import Application as BaseApplication
from abilian.core.celery import FlaskCelery as BaseCelery
from abilian.core.celery import FlaskLoader as CeleryBaseLoader
from abilian.services import converter

from .apps.documents.repository import repository
from .extension import sbe

# Used for side effects, do not remove

__all__ = ["create_app", "Application"]

logger = logging.getLogger(__name__)


def create_app(config=None):
    return Application(config=config)


# loader to be used by celery workers
class CeleryLoader(CeleryBaseLoader):
    flask_app_factory = "abilian.sbe.app.create_app"


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
        # "abilian.sbe.apps.calendar",
        "abilian.sbe.apps.communities",
        "abilian.sbe.apps.social",
        "abilian.sbe.apps.preferences",
    )

    def __init__(self, name="abilian_sbe", config=None, **kwargs):
        BaseApplication.__init__(self, name, config=config, **kwargs)
        loader = jinja2.PackageLoader("abilian.sbe", "templates")
        self.register_jinja_loaders(loader)

    def init_extensions(self):
        BaseApplication.init_extensions(self)
        sbe.init_app(self)
        repository.init_app(self)
        converter.init_app(self)
