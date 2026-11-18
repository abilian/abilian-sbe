# Copyright (c) 2012-2026, Abilian SAS

"""One's account on one page: name, language, the daily digest, the password; the
address shown, not changed."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING

from flask import url_for

from abilian.sbe.apps.preferences.panels.account import DAILY
from abilian.services import get_service
from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy


def _form(user: User, **changes: str) -> dict[str, str]:
    return {
        "first_name": user.first_name or "Pat",
        "last_name": user.last_name or "Doe",
        "locale": "fr",
        "timezone": "Europe/Paris",
        "password": "",
        "confirm_password": "",
        **changes,
    }


def test_my_account_shows_my_address_without_a_field_for_it(
    client: FlaskClient, user: User
) -> None:
    with client_login(client, user):
        response = client.get(url_for("preferences.index"), follow_redirects=True)

    assert response.status_code == 200
    html = unescape(response.get_data(as_text=True))
    assert "My account" in html
    assert user.email in html
    assert 'name="email"' not in html


def test_my_account_saves_my_name_and_the_daily_digest(
    client: FlaskClient, user: User, db: SQLAlchemy
) -> None:
    with client_login(client, user):
        response = client.post(
            url_for("preferences.user_post"),
            data=_form(user, first_name="Renamed", daily="y"),
        )

    assert response.status_code == 302
    db.session.expire_all()
    assert user.first_name == "Renamed"
    assert get_service("preferences").get_preferences(user)[DAILY] is True


def test_a_weak_new_password_is_refused_under_its_field(
    client: FlaskClient, user: User
) -> None:
    too_short = "Ab1"
    with client_login(client, user):
        response = client.post(
            url_for("preferences.user_post"),
            data=_form(user, password=too_short, confirm_password=too_short),
        )

    assert response.status_code == 200
    html = unescape(response.get_data(as_text=True))
    assert 'id="password-error"' in html
    assert "at least 8 characters" in html


def test_a_photo_takes_the_place_of_the_initials(
    client: FlaskClient, user: User, db: SQLAlchemy
) -> None:
    photo = url_for("users.photo", user_id=user.id)
    with client_login(client, user):
        before = client.get(url_for("preferences.user")).get_data(as_text=True)
        user.photo = b"a photo, as far as this page goes"
        db.session.commit()
        after = client.get(url_for("preferences.user")).get_data(as_text=True)

    assert photo not in before
    assert f'<img src="{photo}"' in after
