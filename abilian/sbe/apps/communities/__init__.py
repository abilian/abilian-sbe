"""Communities module."""
from flask import Flask


def register_plugin(app: Flask) -> None:
    # Used for side-effect
    from . import events  # noqa
    from . import search
    from .views import communities

    app.register_blueprint(communities)

    search.init_app(app)
