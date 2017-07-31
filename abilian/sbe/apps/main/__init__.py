"""Register extensions as a plugin.

NOTE: panels are currently loaded and registered manually. This may change
in the future.
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe


def register_plugin(app):
    sbe.init_app(app)
    from .main import blueprint
    app.register_blueprint(blueprint)
