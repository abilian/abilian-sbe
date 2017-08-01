"""
Default ("home") page for social apps.
"""
from __future__ import absolute_import


def register_plugin(app):
    from .views.social import social  # noqa
    from .views import users, groups, sidebars  # noqa

    app.register_blueprint(social)

    # TODO: better config variable choice?
    if app.config.get("SOCIAL_REST_API"):
        from .restapi import restapi
        app.register_blueprint(restapi)
