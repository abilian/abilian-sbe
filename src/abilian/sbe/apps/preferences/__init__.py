# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

import jinja2

from abilian.services.preferences import preferences

from .panels.account import AccountPanel

if TYPE_CHECKING:
    from abilian.app import Application


def register_plugin(app: Application) -> None:
    loader = jinja2.PackageLoader("abilian.sbe.apps.preferences")
    app.register_jinja_loaders(loader)
    preferences.register_panel(AccountPanel(), app)
