# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import uuid
from importlib import resources as rso
from typing import TYPE_CHECKING

from loguru import logger

from abilian.core.util import fqcn
from abilian.sbe import ui

# Asset management now handled by Vite

if TYPE_CHECKING:
    from collections.abc import Callable

    from abilian.app import Application


STATIC_DIR = str(rso.files("abilian.sbe") / "static")


class AbilianSBE:
    """Base extension required by abilian.sbe.apps."""

    def __init__(self, app: Application | None = None) -> None:
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Application) -> None:
        # False: it's ok if the antivirus task was run, but service couldn't get a
        # result
        app.config.setdefault("ANTIVIRUS_CHECK_REQUIRED", False)
        app.config.setdefault("SBE_FORUM_REPLY_BY_MAIL", False)

        if FQCN in app.extensions:
            return

        app.extensions[FQCN] = self

        # register i18n
        app.extensions["babel"].add_translations("abilian.sbe")

        # sbe static assets
        app.add_static_url("abilian/sbe", STATIC_DIR, endpoint="abilian_sbe_static")
        # Note: SBE-specific assets are now handled by Vite or included in components

        # Jinja
        logger.info("Register jinja context processors")
        app.context_processor(inject_template_utils)
        ui.register(app)


FQCN = fqcn(AbilianSBE)
sbe = AbilianSBE()


def inject_template_utils() -> dict[str, Callable]:
    from abilian.sbe.apps.communities.security import can_manage
    from abilian.sbe.apps.forum.security import can_write as can_write_post

    return {
        "uuid": uuid.uuid1,
        "can_manage": can_manage,
        "can_write_post": can_write_post,
    }
