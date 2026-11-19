# Copyright (c) 2012-2026, Abilian SAS

"""What the site depends on, and whether it answers: the database, the task queue,
document conversion, the antivirus, the search index, the mail server. Each check
asks the thing itself, briefly, when the overview is shown."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING

import redis
import sqlalchemy as sa
from flask import current_app

from abilian.core.extensions import db
from abilian.i18n import _
from abilian.services import get_service
from abilian.services.antivirus import service as antivirus_service
from abilian.services.conversion.handlers import HAS_LIBREOFFICE, HAS_PDFTOTEXT

if TYPE_CHECKING:
    from collections.abc import Callable

#: How long what the site depends on has to answer, in seconds.
ANSWER_TIMEOUT = 2


@dataclass(frozen=True)
class Check:
    """A thing the site depends on: its name, whether it answers, a word on it."""

    name: str
    ok: bool
    note: str


def site_health() -> list[Check]:
    """Every check, in the order the overview lists them."""
    return [check() for check in CHECKS]


def database() -> Check:
    name = _("Database")
    try:
        db.session.execute(sa.text("SELECT 1"))
    except sa.exc.OperationalError as e:
        return Check(name, False, str(e.orig))
    dialect = db.engine.dialect
    version = ".".join(str(part) for part in dialect.server_version_info or ())
    return Check(name, True, f"{dialect.name} {version}".strip())


def task_queue() -> Check:
    """The task broker Dramatiq sends to, asked briefly: a host that drops packets
    must not hold the page."""
    name = _("Task queue")
    url = current_app.config.get("DRAMATIQ_BROKER_URL")
    if not url:
        return Check(name, False, _("Redis is not configured."))
    broker = redis.Redis.from_url(
        url, socket_connect_timeout=ANSWER_TIMEOUT, socket_timeout=ANSWER_TIMEOUT
    )
    try:
        broker.ping()
    except redis.exceptions.RedisError as e:
        return Check(name, False, str(e))
    return Check(name, True, _("Redis answers."))


def conversion() -> Check:
    name = _("Document conversion")
    missing = [
        tool
        for tool, found in (
            ("LibreOffice", HAS_LIBREOFFICE),
            ("Poppler", HAS_PDFTOTEXT),
        )
        if not found
    ]
    if missing:
        return Check(name, False, _("Missing: %(tools)s.", tools=", ".join(missing)))
    return Check(name, True, "LibreOffice, Poppler")


def antivirus() -> Check:
    name = _("Antivirus")
    problem = antivirus_service.problem()
    if problem is not None:
        return Check(name, False, _("Files are not scanned: %(why)s.", why=problem))
    return Check(name, True, _("ClamAV answers."))


def search_index() -> Check:
    name = _("Search index")
    indexes = get_service("indexing").app_state.indexes
    if "default" not in indexes:
        return Check(name, False, _("The index is not open."))
    count = indexes["default"].doc_count()
    return Check(name, True, _("%(count)d objects.", count=count))


def mail() -> Check:
    name = _("Sending e-mails")
    config = current_app.config
    if config.get("MAIL_SUPPRESS_SEND"):
        return Check(name, False, _("Sending is turned off."))
    server = config.get("MAIL_SERVER", "localhost")
    port = config.get("MAIL_PORT", 25)
    try:
        socket.create_connection((server, port), timeout=ANSWER_TIMEOUT).close()
    except OSError as e:
        return Check(name, False, f"{server}:{port}: {e}")
    return Check(name, True, f"{server}:{port}")


CHECKS: tuple[Callable[[], Check], ...] = (
    database,
    task_queue,
    conversion,
    antivirus,
    search_index,
    mail,
)
