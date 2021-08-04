"""Communities module."""
from __future__ import annotations

from flask import Flask


def register_plugin(app: Flask):
    # Used for side-effect
    from . import events  # noqa
    from . import search
    from .views import communities

    app.register_blueprint(communities)

    search.init_app(app)
