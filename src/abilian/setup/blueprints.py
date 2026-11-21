# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


def setup_blueprints(app: Flask) -> None:
    from abilian.web import health
    from abilian.web.coreviews import users
    from abilian.web.views.images import images_bp

    app.register_blueprint(health.blueprint)
    app.register_blueprint(images_bp)
    app.register_blueprint(users.blueprint)
