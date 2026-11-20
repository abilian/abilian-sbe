# Copyright (c) 2026, Abilian SAS

"""A page that cannot be shown says why, in words, and the way back."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING

from flask import render_template, url_for

from tests.util import client_login

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User


def test_a_page_that_does_not_exist(client: FlaskClient, user: User) -> None:
    with client_login(client, user):
        response = client.get("/no/such/page")

    assert response.status_code == 404
    html = unescape(response.get_data(as_text=True))
    assert "This page does not exist" in html
    assert url_for("main.home") in html


def test_a_page_one_may_not_see(client: FlaskClient, user: User) -> None:
    with client_login(client, user):
        response = client.get(url_for("admin.dashboard"))

    assert response.status_code == 403
    assert "You may not see this page" in unescape(response.get_data(as_text=True))


def test_the_server_error_page_needs_nobody_signed_in(app: Flask) -> None:
    """It is drawn when anything may have failed, the database included."""
    with app.test_request_context():
        html = unescape(render_template("error500.html", error=None))

    assert "Something went wrong" in html
