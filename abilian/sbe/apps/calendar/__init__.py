# coding=utf-8
"""Calendar module."""


def register_plugin(app):
    from .views import blueprint
    from .actions import register_actions

    blueprint.record_once(register_actions)
    app.register_blueprint(blueprint)
