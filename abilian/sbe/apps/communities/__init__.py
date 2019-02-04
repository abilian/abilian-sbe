# coding=utf-8
"""Communities module."""


def register_plugin(app):
    # Used for side-effect
    from . import events  # noqa
    from .views import communities
    from . import search

    app.register_blueprint(communities)

    search.init_app(app)
