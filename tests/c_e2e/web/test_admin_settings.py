# Copyright (c) 2012-2026, Abilian SAS

"""The site's settings: saved from the administration, read by each process as it
starts, and summed up on the overview."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import url_for

from abilian.services import settings_service
from abilian.setup import load_stored_settings
from abilian.web.admin.panels.settings import digest_hour
from tests.util import client_login

if TYPE_CHECKING:
    import pytest
    from flask import Flask
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy


def test_the_digest_leaves_at_the_hour_chosen(
    app: Flask,
    client: FlaskClient,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(app.config, "SITE_NAME", app.config.get("SITE_NAME"))
    monkeypatch.setitem(app.config, "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST", "0 10 * * *")
    form = {
        "action": "save",
        "SITE_NAME": "Our extranet",
        "MAIL_SENDER": "extranet@example.org",
        "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST": "7",
    }

    with client_login(client, admin_user):
        client.post(url_for("admin.settings"), data=form)
        overview = unescape(
            client.get(url_for("admin.dashboard")).get_data(as_text=True)
        )

    stored = settings_service.namespace("config").as_dict()
    assert stored["SCHEDULE_SEND_DAILY_SOCIAL_DIGEST"] == "0 7 * * *"
    card = overview.split('id="settings"')[1].split("</section>")[0]
    assert "<dd>Our extranet</dd>" in card
    assert "<dd>at 07:00</dd>" in card


def test_an_hour_out_of_the_day_is_refused(
    app: Flask, client: FlaskClient, admin_user: User
) -> None:
    form = {"action": "save", "SITE_NAME": "x", "MAIL_SENDER": "x"}

    with client_login(client, admin_user):
        response = client.post(
            url_for("admin.settings"),
            data={**form, "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST": "25"},
        )

    assert response.status_code == 400


def test_a_schedule_set_otherwise_is_not_an_hour() -> None:
    assert digest_hour({"SCHEDULE_SEND_DAILY_SOCIAL_DIGEST": "0 7 * * *"}) == 7
    assert digest_hour({"SCHEDULE_SEND_DAILY_SOCIAL_DIGEST": "30 7 * * 1"}) is None
    assert digest_hour({}) == 10


def test_a_process_starts_with_the_settings_saved(
    app: Flask, db: SQLAlchemy, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(app.config, "SITE_NAME", "From the files")
    settings_service.namespace("config").set("SITE_NAME", "Saved", "string")
    db.session.commit()

    load_stored_settings(app)

    assert app.config["SITE_NAME"] == "Saved"


def test_a_digest_turned_off_stays_off(
    app: Flask,
    client: FlaskClient,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(app.config, "SITE_NAME", app.config.get("SITE_NAME"))
    monkeypatch.setitem(app.config, "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST", "")
    form = {"action": "save", "SITE_NAME": "x", "MAIL_SENDER": "x"}

    with client_login(client, admin_user):
        page = client.get(url_for("admin.settings")).get_data(as_text=True)
        client.post(
            url_for("admin.settings"),
            data={**form, "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST": "off"},
        )
        overview = unescape(
            client.get(url_for("admin.dashboard")).get_data(as_text=True)
        )

    assert '<option value="off" selected>' in page
    assert (
        settings_service.namespace("config").get("SCHEDULE_SEND_DAILY_SOCIAL_DIGEST")
        == ""
    )
    assert "<dd>not sent</dd>" in overview


def test_a_process_starts_on_its_files_when_the_database_does_not_answer(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_answer(engine) -> None:
        statement = "SELECT 1"
        raise sa.exc.OperationalError(statement, {}, Exception("refused"))

    monkeypatch.setitem(app.config, "SITE_NAME", "From the files")
    monkeypatch.setattr(sa, "inspect", no_answer)

    load_stored_settings(app)

    assert app.config["SITE_NAME"] == "From the files"
