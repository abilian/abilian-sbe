"""Static configuration for the application.

TODO: add more (runtime) flexibility in plugin discovery, selection
and activation.
"""
import logging
from typing import Optional, Type

import jinja2

from abilian.app import Application as BaseApplication
from abilian.core.celery import FlaskLoader as CeleryBaseLoader
from abilian.services import converter

from .apps.documents.repository import repository
from .extension import sbe

# Used for side effects, do not remove


__all__ = ["create_app", "Application"]

logger = logging.getLogger(__name__)


# loader to be used by celery workers
class CeleryLoader(CeleryBaseLoader):
    flask_app_factory = "abilian.sbe.app.create_app"


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

    def setup(self, config: Optional[Type]) -> None:
        super().setup(config)
        loader = jinja2.PackageLoader("abilian.sbe", "templates")
        self.register_jinja_loaders(loader)

    def init_extensions(self) -> None:
        BaseApplication.init_extensions(self)
        sbe.init_app(self)
        repository.init_app(self)
        converter.init_app(self)


def create_app(config: Optional[Type] = None, **kw) -> Application:
    app = Application(**kw)
    app.setup(config)
    return app
