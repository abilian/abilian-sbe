# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from flask import request, url_for

from abilian.core.models.subjects import User
from abilian.services.auth import views

if TYPE_CHECKING:
    from flask.ctx import AppContext
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from abilian.app import Application


def test_get_redirect_target(app: Application, app_context: AppContext) -> None:
    get_redirect_target = views.get_redirect_target
    form_url = partial(url_for, "login.login_form")

    with app.test_request_context(form_url()):
        assert get_redirect_target() == ""
        url_root = request.url_root[:-1]

    with app.test_request_context(form_url(next="/")):
        assert get_redirect_target() == f"{url_root}/"

    # test "next" from referer
    referrer = f"{url_root}/some/path"
    with app.test_request_context(form_url(), headers=[("Referer", referrer)]):
        assert get_redirect_target() == referrer

    # don't cycle if coming from 'login.*' page, like this kind of cycle:
    # forgot password form ->  login page -> success
    # -> redirect(next = forgot password form) -> ...
    referrer = url_root + url_for("login.forgotten_pw")
    with app.test_request_context(form_url(), headers=[("Referer", referrer)]):
        assert get_redirect_target() == ""

    # test open redirect is forbidden
    with app.test_request_context(form_url(next="http://google.com/test")):
        assert get_redirect_target() == ""

    # open redirect through malicious construct and browser not checking
    # Location
    with app.test_request_context(form_url(next="/////google.com")):
        assert get_redirect_target() == f"{url_root}///google.com"


def test_login_post(session: Session, client: FlaskClient) -> None:
    kwargs = {"email": "User@domain.tld", "password": "azerty", "can_login": True}
    user = User(**kwargs)
    session.add(user)
    session.flush()

    response = client.post("/user/login", data=kwargs)
    assert response.status_code == 302

    # wrong password
    d = dict(kwargs)
    d["password"] = "wrong one"  # noqa: S105
    response = client.post("/user/login", data=d)
    assert response.status_code == 401

    # login disabled
    user.can_login = False
    session.flush()
    response = client.post("/user/login", data=kwargs)
    assert response.status_code == 401


def test_api_post(session: Session, client: FlaskClient) -> None:
    kwargs = {"email": "User@domain.tld", "password": "azerty", "can_login": True}
    user = User(**kwargs)
    session.add(user)
    session.flush()

    response = client.post(
        "/user/api/login", data=json.dumps(kwargs), content_type="application/json"
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "email": "User@domain.tld",
        "username": "user@domain.tld",
        "fullname": "User",
        "next_url": "",
    }

    response = client.post("/user/api/logout")
    assert response.status_code == 200


def test_forgotten_pw(app: Application, session: Session, client: FlaskClient) -> None:
    mail = app.extensions["mail"]
    kwargs = {"email": "User@domain.tld", "password": "azerty", "can_login": True}
    user = User(**kwargs)
    session.add(user)
    session.flush()

    payload = dict(**kwargs)
    del payload["password"]

    with mail.record_messages() as outbox:
        response = client.post("/user/forgotten_pw", data=payload)
        assert response.status_code == 302
        assert len(outbox) == 1

        msg = outbox[0]
        assert msg.subject == "Password reset instruction for Abilian Test"
        assert msg.recipients == ["User@domain.tld"]
        assert msg.cc == []


def test_the_forgotten_password_form_does_not_tell_who_has_an_account(
    app: Application, session: Session, client: FlaskClient
) -> None:
    """An unknown address gets the same answer as a known one, and no e-mail."""
    mail = app.extensions["mail"]
    known = User(email="known@domain.tld", password=uuid4().hex, can_login=True)
    session.add(known)
    session.flush()

    answers, messages = [], []
    with mail.record_messages() as outbox:
        for email in ("known@domain.tld", "nobody@domain.tld"):
            answer = client.post(url_for("login.forgotten_pw"), data={"email": email})
            answers.append(answer)
            messages.append(client.get(answer.location).get_data(as_text=True))

    assert [answer.status_code for answer in answers] == [302, 302]
    assert answers[0].location == answers[1].location
    assert "nobody@domain.tld" not in messages[1]
    assert "If an account uses this address" in messages[1]
    assert [message.recipients for message in outbox] == [["known@domain.tld"]]


def test_a_new_password_has_at_least_eight_characters(
    app: Application, session: Session, client: FlaskClient
) -> None:
    """Seven were accepted, while the message asked for eight."""
    user = User(
        first_name="Ann",
        last_name="Lee",
        email="user@domain.tld",
        password=uuid4().hex,
        can_login=True,
    )
    session.add(user)
    session.flush()
    token = views.generate_reset_password_token(user)
    url = url_for("login.reset_password_post", token=token)

    refused = client.post(url, data={"password": "Abcdef1"})
    accepted = client.post(url, data={"password": "Abcdefg1"})

    assert refused.location.endswith(url)
    assert accepted.location.startswith(url_for("login.login_form"))
    assert user.authenticate("Abcdefg1")


def test_a_password_link_opens_nothing_once_used(
    app: Application, session: Session, client: FlaskClient
) -> None:
    """A forwarded invitation must not let someone else choose the password again."""
    user = User(
        first_name="Ann",
        last_name="Lee",
        email="user@domain.tld",
        password=uuid4().hex,
        can_login=True,
    )
    session.add(user)
    session.flush()
    token = views.generate_reset_password_token(user)
    url = url_for("login.reset_password_post", token=token)

    client.post(url, data={"password": "Abcdefg1"})
    again = client.post(url, data={"password": "Hijklmn2"})

    assert again.location.endswith(url_for("login.forgotten_pw"))
    assert user.authenticate("Abcdefg1")
    assert not user.authenticate("Hijklmn2")
