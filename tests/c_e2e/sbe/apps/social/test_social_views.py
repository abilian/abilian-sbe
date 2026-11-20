# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import pytest
from flask import url_for

from tests.util import client_login


def test_home_moved_to_my_feed(client, login_admin) -> None:
    response = client.get(url_for("social.home"))
    assert response.status_code == 302


def test_users(client, login_admin) -> None:
    response = client.get(url_for("social.users"))
    assert response.status_code == 200


def test_user(client, login_admin) -> None:
    user = login_admin
    response = client.get(url_for("social.user", user_id=user.id))
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("endpoint", "kwargs"),
    [
        ("social.user", {"user_id": 999999}),
    ],
)
def test_an_unknown_user_is_not_found(client, login_admin, endpoint, kwargs) -> None:
    assert client.get(url_for(endpoint, **kwargs)).status_code == 404


def test_editing_a_profile_leads_where_it_is_done(
    client, user, admin_user, db_session
) -> None:
    """One's own on one's account page, another's in the administration."""
    url = url_for("social.user_edit", user_id=admin_user.id)

    with client_login(client, user):
        assert client.get(url).status_code == 403
        own = client.get(url_for("social.user_edit", user_id=user.id))
        assert own.headers["Location"].endswith(url_for("preferences.user"))

    with client_login(client, admin_user):
        response = client.get(url_for("social.user_edit", user_id=user.id))
    assert response.headers["Location"].endswith(
        url_for("admin.users_user", user_id=user.id)
    )
