# Copyright (c) 2012-2024, Abilian SAS

"""Who may change a group's membership and its administrators.

`group_post` handles add, remove, add-admin and remove-admin, and its only
authorization was `assert is_admin(group)`. Two things wrong with that:

- `assert` is compiled out under `python -O`, so on an optimised interpreter
  the check is not there at all and any authenticated user can POST
  `action=add-admin&user=<themselves>` and become an administrator of any
  group -- which then lets them add and remove its members.
- Even with assertions on it raises `AssertionError`, so a refused request is
  a 500 with a traceback rather than a 403.

Authorization is not an invariant to assert; it is an answer to give. These
pin the answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for
from pytest import fixture

from abilian.core.extensions import db as db_
from abilian.core.models.subjects import Group, User
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


@fixture
def group(db: SQLAlchemy) -> Group:
    g = Group(name="A group")
    db.session.add(g)
    db.session.flush()
    return g


def _user(db: SQLAlchemy, email: str) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    return user


@fixture
def outsider(db: SQLAlchemy) -> User:
    return _user(db, "outsider@example.com")


@fixture
def group_admin(db: SQLAlchemy, group: Group) -> User:
    admin = _user(db, "group-admin@example.com")
    group.admins.add(admin)
    db.session.flush()
    return admin


def _post(client: FlaskClient, group: Group, **form):
    return client.post(url_for("social.group_post", group_id=group.id), data=form)


def test_a_stranger_cannot_make_themselves_an_admin(
    group: Group, outsider: User, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """The escalation itself: admin of a group can then add and remove its
    members."""
    ensure_services_started(["security"])

    with client_login(client, outsider):
        response = _post(client, group, action="add-admin", user=str(outsider.id))

    db_.session.expire_all()
    assert response.status_code == 403, "a refusal, not an AssertionError"
    assert outsider not in group.admins


def test_a_stranger_cannot_add_a_member(
    group: Group, outsider: User, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    ensure_services_started(["security"])
    victim = _user(db, "victim@example.com")

    with client_login(client, outsider):
        response = _post(client, group, action="add", user=str(victim.id))

    db_.session.expire_all()
    assert response.status_code == 403
    assert victim not in group.members


def test_a_group_admin_still_can(
    group: Group,
    group_admin: User,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """The fix must not take the feature from the people it is for."""
    ensure_services_started(["security"])
    newcomer = _user(db, "newcomer@example.com")

    with client_login(client, group_admin):
        response = _post(client, group, action="add", user=str(newcomer.id))

    db_.session.expire_all()
    assert response.status_code in (200, 302)
    assert newcomer in group.members


def test_anyone_may_still_join_and_leave(
    group: Group, outsider: User, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """`join` and `leave` are deliberately outside the admin check."""
    ensure_services_started(["security"])

    with client_login(client, outsider):
        assert _post(client, group, action="join").status_code in (200, 302)
        db_.session.expire_all()
        assert outsider in group.members

        assert _post(client, group, action="leave").status_code in (200, 302)
        db_.session.expire_all()
        assert outsider not in group.members
