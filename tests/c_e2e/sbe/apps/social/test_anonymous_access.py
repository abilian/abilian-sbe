# Copyright (c) 2012-2024, Abilian SAS

"""The user directory is for people who are logged in.

`/users/json/?q=ad` answered an anonymous request with the email, id and name
of every user whose name starts with "ad", so anyone who could reach the site
could list every account two letters at a time. The `social` blueprint had the
same gap on most of its routes: each route was expected to carry its own
`@login_required`, and most did not.

Both blueprints now refuse anonymous visitors as a whole, so a route added
later cannot forget to. So does `preferences`, whose panels all edit the
visitor's own settings and crashed on an anonymous one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import url_for

from abilian.core.models.subjects import Group
from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy

GUARDED_BLUEPRINTS = ("users", "social", "preferences")


def _guarded_get_endpoints(app: Application) -> list[str]:
    return sorted(
        rule.endpoint
        for rule in app.url_map.iter_rules()
        if rule.endpoint.split(".")[0] in GUARDED_BLUEPRINTS and "GET" in rule.methods
    )


def test_every_guarded_get_route_sends_an_anonymous_visitor_to_login(
    app: Application, client: FlaskClient, user: User, db: SQLAlchemy
) -> None:
    group = Group(name="A group")
    db.session.add(group)
    db.session.flush()
    ids = {"user_id": user.id, "group_id": group.id, "stream_name": "all"}

    refused = {}
    for endpoint in _guarded_get_endpoints(app):
        rule = next(app.url_map.iter_rules(endpoint))
        url = url_for(endpoint, **{arg: ids[arg] for arg in rule.arguments})
        response = client.get(url)
        if response.status_code != 302 or "/login" not in response.location:
            refused[url] = response.status_code

    assert not refused, f"not sent to login: {refused}"


@pytest.mark.parametrize(
    "endpoint", ["users.json_list", "social.users_json", "social.users"]
)
def test_the_user_directory_tells_an_anonymous_visitor_nothing(
    endpoint: str, client: FlaskClient, user: User
) -> None:
    response = client.get(
        url_for(endpoint, q="jo"),
        headers={"Accept": "application/json"},
    )

    assert user.email not in response.get_data(as_text=True)


def test_a_logged_in_user_still_finds_people(
    client: FlaskClient, user: User, db_session
) -> None:
    """The member pickers depend on these endpoints."""
    with client_login(client, user):
        response = client.get(
            url_for("social.users_json", q="jo"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    assert user.email in response.get_data(as_text=True)


@pytest.mark.parametrize("args", [{}, {"q": "j"}, {"q": "%"}])
def test_the_user_picker_refuses_a_missing_or_short_query(
    args: dict[str, str], client: FlaskClient, user: User, db_session
) -> None:
    with client_login(client, user):
        response = client.get(url_for("social.users_json", **args))

    assert response.status_code == 400
