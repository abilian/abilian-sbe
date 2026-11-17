# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import pytest
from flask import url_for

from abilian.core.models.subjects import Group
from tests.util import client_login


def test_home_moved_to_my_feed(client, login_admin) -> None:
    response = client.get(url_for("social.home"))
    assert response.status_code == 302


def test_users(client, login_admin) -> None:
    response = client.get(url_for("social.users"))
    assert response.status_code == 200


def test_groups(client, login_admin) -> None:
    response = client.get(url_for("social.groups"))
    assert response.status_code == 200


def test_user(client, login_admin) -> None:
    user = login_admin
    response = client.get(url_for("social.user", user_id=user.id))
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("endpoint", "kwargs"),
    [
        ("social.group_home", {"group_id": 999999}),
        ("social.group_json", {"group_id": 999999}),
        ("social.user", {"user_id": 999999}),
    ],
)
def test_an_unknown_group_or_user_is_not_found(
    client, login_admin, endpoint, kwargs
) -> None:
    assert client.get(url_for(endpoint, **kwargs)).status_code == 404


def test_my_groups_lists_the_users_groups_by_name(
    client, login_admin, db_session
) -> None:
    """`groups` is a set: sorting it in place crashed this tab."""
    user = login_admin
    groups = [Group(name="Zeta"), Group(name="Alpha")]
    db_session.add_all(groups)
    db_session.flush()
    for group in groups:
        user.join(group)
    db_session.commit()

    response = client.get(url_for("social.groups", tab="my_groups"))

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert page.index("Alpha") < page.index("Zeta")


def test_only_the_owner_or_an_admin_edits_a_profile(
    client, user, admin_user, db_session
) -> None:
    url = url_for("social.user_edit", user_id=admin_user.id)

    with client_login(client, user):
        assert client.get(url).status_code == 403
        form = {"first_name": "Changed", "__action": "edit"}
        assert client.post(url, data=form).status_code == 403
    db_session.expire_all()
    assert admin_user.first_name != "Changed"

    with client_login(client, admin_user):
        assert client.get(url).status_code == 200
