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
    ("site_name", "title"),
    [("Acme Intranet", "Signing in · Acme Intranet"), ("", "Signing in")],
)
def test_the_sign_in_page_names_the_site_only_when_there_is_one(
    site_name: str, title: str, app: Flask, client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty SITE_NAME used to leave the heading reading "Login to"."""
    monkeypatch.setitem(app.config, "SITE_NAME", site_name)

    html = client.get(url_for("login.login_form")).get_data(as_text=True)

    found = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    assert found is not None
    assert found.group(1) == title
    assert ('class="sbe-brandname"' in html) == bool(site_name)
