# Copyright (c) 2012-2026, Abilian SAS

"""Signing in on the Abilian Design System: SBE's pages over Abilian Core's.

What the views check is in `tests/c_e2e/services/test_auth.py`.
"""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

from flask import url_for

from abilian.core.models.subjects import User
from abilian.services.auth import views

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

#: Generated: the tests need one, not a particular one.
SECRET = f"Az1{uuid4().hex}"


def test_the_sign_in_page_has_no_bar_and_says_where_accounts_come_from(
    client: FlaskClient,
) -> None:
    response = client.get(url_for("login.login_form"))

    html = unescape(response.get_data(as_text=True))
    assert response.status_code == 200
    assert '<body class="ads-centered">' in html
    assert 'autocomplete="current-password"' in html
    assert url_for("login.forgotten_pw_form") in html
    assert "The managers of your communities invite you" in html


def test_a_wrong_password_comes_back_with_the_error_and_the_address(
    session: Session, client: FlaskClient
) -> None:
    session.add(User(email="user@domain.tld", password=SECRET, can_login=True))
    session.flush()

    response = client.post(
        url_for("login.login_post"),
        data={"email": "user@domain.tld", "password": "wrong"},
    )

    html = unescape(response.get_data(as_text=True))
    assert response.status_code == 401
    alert = html.split('class="ads-alert ads-tone-danger" role="alert"')[1]
    assert "Sorry, wrong password." in alert.split("</div>")[0]
    assert 'value="user@domain.tld"' in html


def test_a_new_password_is_for_someone_and_says_the_rules(
    session: Session, client: FlaskClient
) -> None:
    user = User(
        first_name="Claire",
        last_name="Moreau",
        email="claire@domain.tld",
        password=SECRET,
        can_login=True,
    )
    session.add(user)
    session.flush()
    token = views.generate_reset_password_token(user)

    response = client.get(url_for("login.reset_password", token=token))

    html = unescape(response.get_data(as_text=True))
    assert response.status_code == 200
    assert "For Claire Moreau (claire@domain.tld)." in html
    assert "At least 8 characters" in html
