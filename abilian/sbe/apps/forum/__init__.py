# coding=utf-8
"""Forum module."""
from __future__ import absolute_import

from abilian.sbe.extension import sbe


def register_plugin(app):
    app.config.setdefault("SBE_FORUM_REPLY_BY_MAIL", False)
    app.config.setdefault("INCOMING_MAIL_USE_MAILDIR", False)
    sbe.init_app(app)
    from .views import forum
    from .actions import register_actions
    from .models import ThreadIndexAdapter
    from .cli import check_email, inject_email
    from . import tasks

    forum.record_once(register_actions)
    app.register_blueprint(forum)
    app.services["indexing"].adapters_cls.insert(0, ThreadIndexAdapter)
    tasks.init_app(app)

    app.cli.add_command(check_email)
    app.cli.add_command(inject_email)
