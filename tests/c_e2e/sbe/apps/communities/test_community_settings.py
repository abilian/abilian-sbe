# Copyright (c) 2012-2024, Abilian SAS

"""A community manager can edit their own community's settings.

`CommunityEdit` was guarded by the site-admin check, so managing a community
stopped at its settings page: the manager who could add and remove members,
moderate its forum and administer its documents could not rename it or change
its type. Only a site admin could, for every community on the instance.

Destroying a community (`CommunityDelete`) and creating one (`CommunityCreate`)
stay site-admin: one is irreversible, and the other is not a community-scoped
question -- there is no community to manage yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for
from pytest import fixture

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, READER
from abilian.services import security_service
from abilian.services.security import ADMIN
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@fixture
def manager(db: SQLAlchemy, community1: Community) -> User:
    return _member(db, community1, "manager@example.com", MANAGER)


def _member(db: SQLAlchemy, community: Community, email: str, role) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.flush()
    return user


def _settings_url(community: Community) -> str:
    return url_for("communities.settings", community_id=community.slug)


def test_a_manager_can_open_the_settings_page(
    community1: Community, manager: User, client: FlaskClient, app: Application
) -> None:
    ensure_services_started(["security"])

    with client_login(client, manager):
        response = client.get(_settings_url(community1))

    assert response.status_code == 200


def test_a_manager_can_rename_their_community(
    community1: Community,
    manager: User,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """The page being reachable is not the point; the POST behind it is."""
    ensure_services_started(["security"])

    with client_login(client, manager):
        response = client.post(
            _settings_url(community1),
            data={
                "name": "Renamed By Its Manager",
                "description": "Renamed by a manager, not an admin",
                "type": community1.type,
                "linked_group": "",
                "__action": "edit",
            },
        )

    db.session.expire_all()
    assert response.status_code == 302, response.get_data(as_text=True)[:500]
    assert community1.name == "Renamed By Its Manager"


def test_a_plain_member_cannot(
    community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    ensure_services_started(["security"])
    reader = _member(db, community1, "reader@example.com", READER)

    with client_login(client, reader):
        response = client.get(_settings_url(community1))

    assert response.status_code == 403


def test_a_site_admin_still_can(
    community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """Widening to managers must not narrow it for admins, who are not
    members of most communities."""
    ensure_services_started(["security"])
    admin = User(email="admin@example.com", password="test", can_login=True)  # noqa: S106
    db.session.add(admin)
    db.session.flush()
    security_service.grant_role(admin, ADMIN)
    db.session.flush()

    with client_login(client, admin):
        response = client.get(_settings_url(community1))

    assert response.status_code == 200
