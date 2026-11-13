# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import re

import pytest
from flask import Flask, jsonify, session, url_for
from flask_login import current_user


def test_test(app: Flask, client, login_user) -> None:
    @app.route("/dump-session")
    def dump_session():
        user = current_user
        return jsonify(
            session=dict(session), first_name=user.first_name, last_name=user.last_name
        )

    response = client.get("/dump-session")
    assert response.status_code == 200

    json = response.json
    assert json["first_name"] == login_user.first_name
    assert json["last_name"] == login_user.last_name


@pytest.mark.parametrize(
    ("site_name", "heading"),
    [("Acme Intranet", "Login to Acme Intranet"), ("", "Login")],
)
def test_the_login_heading_names_the_site_only_when_there_is_one(
    site_name: str, heading: str, app: Flask, client
) -> None:
    """An empty SITE_NAME used to leave the heading reading "Login to"."""
    app.config["SITE_NAME"] = site_name

    html = client.get(url_for("login.login_form")).get_data(as_text=True)

    h2 = re.search(r"<h2[^>]*>\s*(.*?)\s*</h2>", html, re.DOTALL)
    assert h2 is not None
    assert h2.group(1) == heading
