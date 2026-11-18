# Copyright (c) 2012-2026, Abilian SAS

"""The overview says what the site depends on, and whether each answers."""

from __future__ import annotations

import socket
from html import unescape
from typing import TYPE_CHECKING

from flask import url_for

from abilian.web.admin.panels import health
from tests.util import client_login

if TYPE_CHECKING:
    import pytest
    from flask import Flask
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User


def test_the_overview_lists_what_the_site_depends_on(
    client: FlaskClient, admin_user: User
) -> None:
    with client_login(client, admin_user):
        html = unescape(client.get(url_for("admin.dashboard")).get_data(as_text=True))

    for name in ("Database", "Task queue", "Document conversion", "Antivirus"):
        assert f"<strong>{name}</strong>" in html
    assert "Search index" in html
    assert "Sending e-mails" in html


def test_the_database_answers(app: Flask) -> None:
    with app.test_request_context():
        assert health.database().ok


def test_missing_conversion_tools_are_named(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "HAS_LIBREOFFICE", False)

    with app.test_request_context():
        check = health.conversion()

    assert not check.ok
    assert "LibreOffice" in check.note


def test_a_mail_server_that_does_not_answer_is_to_look_at(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A port nothing listens on: bound, then closed.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setitem(app.config, "MAIL_SUPPRESS_SEND", False)
    monkeypatch.setitem(app.config, "MAIL_SERVER", "127.0.0.1")
    monkeypatch.setitem(app.config, "MAIL_PORT", port)

    with app.test_request_context():
        check = health.mail()

    assert not check.ok
    assert f"127.0.0.1:{port}" in check.note


def test_a_mail_server_that_answers_is_running(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        monkeypatch.setitem(app.config, "MAIL_SUPPRESS_SEND", False)
        monkeypatch.setitem(app.config, "MAIL_SERVER", "127.0.0.1")
        monkeypatch.setitem(app.config, "MAIL_PORT", server.getsockname()[1])

        with app.test_request_context():
            assert health.mail().ok
