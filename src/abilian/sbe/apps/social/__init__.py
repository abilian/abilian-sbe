# Copyright (c) 2012-2024, Abilian SAS

"""Default ("home") page for social apps."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from abilian.app import Application


def register_plugin(app: Application) -> None:
    from .views import groups, sidebars, users
    from .views.social import social

    app.register_blueprint(social)
