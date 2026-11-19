# Copyright (c) 2012-2026, Abilian SAS

"""Signing in on the Abilian Design System: SBE's pages over Abilian Core's.

What the views check is in `tests/c_e2e/services/test_auth.py`.
"""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
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


@pytest.mark.parametrize(
    ("email", "password"),
    [("user@domain.tld", "wrong"), ("nobody@domain.tld", SECRET)],
)
def test_a_failed_sign_in_comes_back_with_the_error_and_the_address(
    email: str, password: str, session: Session, client: FlaskClient
) -> None:
    """A wrong password and an unknown address get the same answer: the form does
    not tell who has an account."""
    session.add(User(email="user@domain.tld", password=SECRET, can_login=True))
    session.flush()

    response = client.post(
        url_for("login.login_post"), data={"email": email, "password": password}
    )

    html = unescape(response.get_data(as_text=True))
    assert response.status_code == 401
    alert = html.split('class="ads-alert ads-tone-danger" role="alert"')[1]
    assert "Wrong email address or password." in alert.split("</div>")[0]
    assert f'value="{email}"' in html


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


def test_an_invited_account_gets_its_names_with_its_password(
    session: Session, client: FlaskClient
) -> None:
    """An invitation made the account without names: its person gives them."""
    user = User(email="dora@domain.tld", can_login=True)
    session.add(user)
    session.flush()
    token = views.generate_reset_password_token(user)
    url = url_for("login.reset_password_post", token=token)

    before = user.password
    page = unescape(client.get(url).get_data(as_text=True))
    nameless = client.post(url, data={"password": SECRET})
    session.refresh(user)
    unchanged = user.password
    named = client.post(
        url, data={"password": SECRET, "first_name": " Dora ", "last_name": "Lune"}
    )
    session.refresh(user)

    assert 'name="first_name"' in page
    assert 'name="last_name"' in page
    assert nameless.location.endswith(url)
    assert unchanged == before
    assert named.status_code == 302
    assert (user.first_name, user.last_name) == ("Dora", "Lune")
    assert user.authenticate(SECRET)
