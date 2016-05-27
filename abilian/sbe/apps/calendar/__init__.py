# coding=utf-8
"""
Calendar module.
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe


def register_plugin(app):
    sbe.init_app(app)

    from .views import blueprint
    from .actions import register_actions
    from .models import Event

    blueprint.record_once(register_actions)
    app.register_blueprint(blueprint)
