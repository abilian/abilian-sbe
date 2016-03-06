# coding=utf-8
""" Communities module
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe


def register_plugin(app):
    sbe.init_app(app)

    # Used for side-effect
    from . import events  # noqa

    from .views import communities
    app.register_blueprint(communities)

    from . import search
    search.init_app(app)
