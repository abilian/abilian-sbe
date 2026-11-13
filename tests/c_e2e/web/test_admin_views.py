# Copyright (c) 2012-2024, Abilian SAS

"""The admin panels, and who may see them.

These used to make no request as any user at all, and assert 200. They passed
because the security service answered True to every question while it was not
running, so what they proved was that the templates render -- not that the
panels are protected. With the service always enforcing, the anonymous case is
what it always should have been, and the interesting assertions are possible
for the first time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import url_for

from abilian.web.admin.panels.sysinfo import installed_packages
from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User

#: Every panel registered by abilian core.
PANELS = [
    "admin.dashboard",
    "admin.sysinfo",
    "admin.login_sessions",
    "admin.audit",
    "admin.settings",
]


def test_list_packages() -> None:
    packages = installed_packages()
    assert isinstance(packages, list)


@pytest.mark.parametrize("endpoint", PANELS)
def test_panel_renders_for_an_admin(
    endpoint: str, client: FlaskClient, admin_user: User, db_session
) -> None:
    with client_login(client, admin_user):
        response = client.get(url_for(endpoint))

    assert response.status_code == 200


@pytest.mark.parametrize("endpoint", PANELS)
def test_panel_refuses_a_plain_user(
    endpoint: str, client: FlaskClient, user: User, db_session
) -> None:
    """The assertion none of these could make before."""
    with client_login(client, user):
        response = client.get(url_for(endpoint))

    assert response.status_code == 403


@pytest.mark.parametrize("endpoint", PANELS)
def test_panel_refuses_an_anonymous_visitor(
    endpoint: str, client: FlaskClient, db_session
) -> None:
    response = client.get(url_for(endpoint))

    assert response.status_code == 403


@pytest.mark.parametrize("args", [{}, {"q": "a"}, {"q": "%"}])
def test_user_search_refuses_a_missing_or_short_query(
    args: dict[str, str], client: FlaskClient, admin_user: User, db_session
) -> None:
    """A query the audit page would never send is the client's mistake: 400,
    not the 500 it used to be."""
    with client_login(client, admin_user):
        response = client.get(url_for("admin.audit_search_users", **args))

    assert response.status_code == 400


def test_user_search_finds_a_user_by_name(
    client: FlaskClient, admin_user: User, user: User, db_session
) -> None:
    with client_login(client, admin_user):
        response = client.get(
            url_for("admin.audit_search_users", q=user.first_name[:3]),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    assert [r["id"] for r in response.json["results"]] == [user.id]


def test_the_audit_log_shows_everything_when_all_contents_is_picked(
    client: FlaskClient, admin_user: User, db_session
) -> None:
    """The filter form always sends `types`, empty for "All contents".

    The base Entity class was offered as a type of its own, with an empty
    entity type, so that empty value matched it and filtered on it, and the
    log came back empty. Picking a day or a user submits the form, so any use
    of the filters emptied the log.
    """
    with client_login(client, admin_user):
        unfiltered = client.get(url_for("admin.audit")).get_data(as_text=True)
        submitted = client.get(url_for("admin.audit", types="", user=""))

    entry = '<li class="flex gap-3'
    assert entry in unfiltered
    assert submitted.get_data(as_text=True).count(entry) == unfiltered.count(entry)
