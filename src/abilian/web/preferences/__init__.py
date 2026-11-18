# Copyright (c) 2012-2024, Abilian SAS

"""A person's own preferences: the "About me" panel, as a plugin an application
may leave out for one of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


def register_plugin(app: Flask) -> None:
    from abilian.services.preferences import preferences

    from .user import UserPreferencesPanel

    preferences.register_panel(UserPreferencesPanel(), app)
