# Copyright (c) 2012-2024, Abilian SAS

"""Static configuration for the application.

TODO: add more (runtime) flexibility in plugin discovery, selection
and activation.
"""

from __future__ import annotations

import jinja2

from abilian.app import Application as BaseApplication, create_app as base_create_app
from abilian.core.dramatiq.setup import init_dramatiq_engine
from abilian.core.plugin_manager import CORE_PLUGINS
from abilian.services import converter

from .apps.documents.repository import content_repository
from .extension import sbe

__all__ = ["create_app"]

SBE_PLUGINS = [
    # One's account is SBE's own page (`apps/preferences`), in place of Core's.
    *(plugin for plugin in CORE_PLUGINS if plugin != "abilian.web.preferences"),
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
]


def create_app(config: type | None = None, **kw) -> BaseApplication:
    kw["plugins"] = SBE_PLUGINS
    app = base_create_app(config=config, **kw)

    with app.app_context():
        content_repository.init_app(app)
        converter.init_app(app)

        loader = jinja2.PackageLoader("abilian.sbe")
        app.register_jinja_loaders(loader)

    sbe.init_app(app)
    init_dramatiq_engine(app)

    return app
