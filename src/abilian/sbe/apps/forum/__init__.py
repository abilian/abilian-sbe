# Copyright (c) 2012-2024, Abilian SAS

"""Forum module."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from abilian.services import get_service

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.services.indexing.service import WhooshIndexService


def register_plugin(app: Application) -> None:
    app.config.setdefault("SBE_FORUM_REPLY_BY_MAIL", False)
    app.config.setdefault("INCOMING_MAIL_USE_MAILDIR", False)

    # from . import tasks
    from .cli import check_email, inject_email
    from .models import ThreadIndexAdapter
    from .views import forum

    app.register_blueprint(forum)
    indexing_service = cast("WhooshIndexService", get_service("indexing"))
    indexing_service.adapters_cls.insert(0, ThreadIndexAdapter)
    # tasks.init_app(app)

    app.cli.add_command(check_email)
    app.cli.add_command(inject_email)
