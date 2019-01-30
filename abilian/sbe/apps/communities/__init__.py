# coding=utf-8
"""Communities module."""


def register_plugin(app):
    # Used for side-effect
    from . import events  # noqa

    from .views import communities

    app.register_blueprint(communities)

    from . import search

    search.init_app(app)
