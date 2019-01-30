# coding=utf-8
"""Register extensions as a plugin.

NOTE: panels are currently loaded and registered manually. This may change
in the future.
"""


def register_plugin(app):
    from .main import blueprint

    app.register_blueprint(blueprint)
