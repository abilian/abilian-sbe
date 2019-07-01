# coding=utf-8
"""Communities module."""
from flask import Flask


def register_plugin(app: Flask) -> None:
    # Used for side-effect
    from . import events  # noqa
    from .views import communities
    from . import search

    app.register_blueprint(communities)

    search.init_app(app)
