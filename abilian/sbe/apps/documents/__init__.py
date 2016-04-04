# coding=utf-8
"""
Folders / Documents module
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe


def register_plugin(app):
    sbe.init_app(app)
    from .views import documents
    from .models import setup_listener
    from .commands import manager
    from . import signals  # noqa
    from . import lock

    app.register_blueprint(documents)
    setup_listener()

    # set default lock lifetime
    app.config.setdefault('SBE_LOCK_LIFETIME', lock.DEFAULT_LIFETIME)

    if app.script_manager:
        app.script_manager.add_command('documents', manager)
