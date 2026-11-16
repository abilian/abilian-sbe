# Copyright (c) 2012-2024, Abilian SAS

"""A group that is not public is seen only by its members and administrators.

The group list already hid it from everyone else, but its page, its member list
and its photo answered anyone logged in, and anyone could join it by posting
`action=join`, which the page does not even offer.
"""

from __future__ import annotations

from secrets import token_hex
from typing import TYPE_CHECKING

import pytest
from flask import url_for

from abilian.core.models.subjects import Group, User
from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


@pytest.fixture
def outsider(db: SQLAlchemy) -> User:
    user = User(email="outsider@example.com", password=token_hex(), can_login=True)
    db.session.add(user)
    return user


def _group(db: SQLAlchemy, *, public: bool) -> Group:
    group = Group(name="A group", public=public)
    db.session.add(group)
    db.session.commit()
    return group


@pytest.mark.parametrize("endpoint", ["group_home", "group_json", "group_mugshot"])
def test_a_private_group_is_not_found_by_an_outsider(
    endpoint: str, client: FlaskClient, db: SQLAlchemy, outsider: User
) -> None:
    group = _group(db, public=False)

    with client_login(client, outsider):
        response = client.get(url_for(f"social.{endpoint}", group_id=group.id))

    assert response.status_code == 404


@pytest.mark.parametrize("endpoint", ["group_home", "group_json", "group_mugshot"])
def test_a_member_sees_their_private_group(
    endpoint: str, client: FlaskClient, db: SQLAlchemy, outsider: User
) -> None:
    group = _group(db, public=False)
    outsider.join(group)
    db.session.commit()

    with client_login(client, outsider):
        response = client.get(url_for(f"social.{endpoint}", group_id=group.id))

    assert response.status_code == 200


def test_an_outsider_cannot_join_a_private_group(
    app: Application, client: FlaskClient, db: SQLAlchemy, outsider: User
) -> None:
    app.config["TRAP_BAD_REQUEST_ERRORS"] = False
    group = _group(db, public=False)

    with client_login(client, outsider):
        url = url_for("social.group_post", group_id=group.id)
        response = client.post(url, data={"action": "join"})

    assert response.status_code == 404
    db.session.expire_all()
    assert outsider not in group.members


def test_anyone_may_join_a_public_group(
    client: FlaskClient, db: SQLAlchemy, outsider: User
) -> None:
    group = _group(db, public=True)

    with client_login(client, outsider):
        url = url_for("social.group_post", group_id=group.id)
        response = client.post(url, data={"action": "join"})

    assert response.status_code == 302
    db.session.expire_all()
    assert outsider in group.members
