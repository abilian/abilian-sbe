# Copyright (c) 2012-2024, Abilian SAS

"""A membership is a role on the community, so the engine can be asked about it.

Memberships used to be projected onto the community's *folder* and nowhere
else. That answered every question about a community's **content** correctly
and left the community itself unanswerable: `has_permission(manager, MANAGE,
community)` was False, which is why `can_manage` had to be hand-written as two
role tests and why `Community.has_permission` raised `ValueError` for anything
but MANAGE.

The community is where a membership means something, so that is where the role
is recorded now. The folder projection stays -- it is what content inherits
from, and per-folder grants remain useful for narrower cases -- but it is a
derived thing rather than the only record.

No `PermissionAssignment` rows are needed for this: the engine's default matrix
already says `MANAGE` belongs to `{ADMIN, MANAGER}` (service.py:70).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.services import security_service
from abilian.services.security import ADMIN, MANAGE, READ, WRITE
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@fixture
def outsider(db: SQLAlchemy) -> User:
    user = User(email="outsider@example.com", can_login=True)
    db.session.add(user)
    db.session.flush()
    return user


def _member(db: SQLAlchemy, community: Community, email: str, role) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.flush()
    return user


def test_a_manager_has_manage_on_the_community_itself(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    """The question the engine could not answer."""
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)

    assert security_service.has_permission(manager, MANAGE, community1)


def test_a_plain_member_does_not(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    ensure_services_started(["security"])
    member = _member(db, community1, "member@example.com", MEMBER)

    assert not security_service.has_permission(member, MANAGE, community1)


def test_an_outsider_does_not(
    app: Application, db: SQLAlchemy, community1: Community, outsider: User
) -> None:
    ensure_services_started(["security"])

    assert not security_service.has_permission(outsider, MANAGE, community1)


def test_a_site_admin_does(
    app: Application, db: SQLAlchemy, community1: Community, outsider: User
) -> None:
    """Without being a member of it: ADMIN is in every permission's role set."""
    ensure_services_started(["security"])
    security_service.grant_role(outsider, ADMIN)
    db.session.flush()

    assert security_service.has_permission(outsider, MANAGE, community1)


def test_the_membership_role_is_the_role_recorded(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)
    member = _member(db, community1, "member@example.com", MEMBER)

    assert security_service.has_role(manager, MANAGER, community1)
    assert security_service.has_role(member, MEMBER, community1)


def test_a_changed_role_replaces_the_old_one(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    """Demotion has to remove, not just add. Otherwise a demoted manager keeps
    MANAGE and the member list says otherwise."""
    ensure_services_started(["security"])
    user = _member(db, community1, "demoted@example.com", MANAGER)
    assert security_service.has_permission(user, MANAGE, community1)

    community1.set_membership(user, MEMBER)
    db.session.flush()

    assert not security_service.has_permission(user, MANAGE, community1)
    assert security_service.has_role(user, MEMBER, community1)


def test_removing_a_membership_removes_the_role(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    ensure_services_started(["security"])
    user = _member(db, community1, "leaving@example.com", MANAGER)

    community1.remove_membership(user)
    db.session.flush()

    assert not security_service.has_permission(user, MANAGE, community1)
    assert security_service.get_roles(user, community1, no_group_roles=True) == []


def test_the_folder_projection_still_works(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    """The community grant is added, not swapped in: content permissions still
    come from the folder, and that is what documents inherit."""
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)
    member = _member(db, community1, "member@example.com", MEMBER)

    assert security_service.has_permission(manager, MANAGE, community1.folder)
    assert security_service.has_permission(member, READ, community1.folder)
    assert not security_service.has_permission(member, WRITE, community1.folder)
