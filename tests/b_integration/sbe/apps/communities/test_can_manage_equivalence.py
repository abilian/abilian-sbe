# Copyright (c) 2012-2024, Abilian SAS

"""`can_manage` moved from reading the member list to asking the engine.

Before: `is_site_admin(user) or community.get_role(user) == MANAGER` -- two
role tests reading `Membership`. After: `has_permission(user, MANAGE,
community)`, reading the `RoleAssignment` that `membership_set` now writes.

That is a change of *source of truth*, so the two have to be shown to agree
rather than assumed to. `_the_old_body` below is the replaced implementation,
kept here so the swap stays checkable; every scenario asserts the engine gives
the same answer.

The deployment consequence, which no test can catch: an existing database has
memberships written before the signal handler existed, and they carry no role
on the community. `flask backfill-community-roles` must run once this code is
installed and before it serves traffic -- the command ships with the change it
repairs, so it cannot run earlier than that -- or every community manager
silently loses MANAGE in the meantime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER, READER, WRITER
from abilian.sbe.apps.communities.security import can_manage
from abilian.services import security_service
from abilian.services.security import ADMIN, is_site_admin
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community

ROLES = [MANAGER, MEMBER, READER, WRITER]


def _the_old_body(community, user) -> bool:
    """What `can_manage` was, verbatim."""
    if user.is_anonymous:
        return False
    if is_site_admin(user):
        return True
    return community is not None and community.get_role(user) == MANAGER


@pytest.fixture
def outsider(db: SQLAlchemy) -> User:
    user = User(email="outsider@example.com", can_login=True)
    db.session.add(user)
    db.session.flush()
    return user


@pytest.mark.parametrize("role", ROLES)
def test_every_membership_role_gives_the_same_answer(
    role, community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    ensure_services_started(["security"])
    community1.set_membership(outsider, role)
    db.session.flush()

    assert can_manage(community1, outsider) == _the_old_body(community1, outsider)


def test_a_non_member_gives_the_same_answer(
    community1: Community, outsider: User, app: Application
) -> None:
    ensure_services_started(["security"])

    assert can_manage(community1, outsider) == _the_old_body(community1, outsider)


def test_a_site_admin_gives_the_same_answer(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    ensure_services_started(["security"])
    security_service.grant_role(outsider, ADMIN)
    db.session.flush()

    assert can_manage(community1, outsider) == _the_old_body(community1, outsider)


def test_no_community_gives_the_same_answer(
    db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """`has_permission(user, MANAGE, None)` asks the global roles, which is
    what the bare admin check did on the same input."""
    ensure_services_started(["security"])

    assert can_manage(None, outsider) == _the_old_body(None, outsider)

    security_service.grant_role(outsider, ADMIN)
    db.session.flush()

    assert can_manage(None, outsider) == _the_old_body(None, outsider)


def test_an_anonymous_user_gives_the_same_answer(
    community1: Community, app: Application
) -> None:
    """The old body refused anonymous before asking anything. The engine has
    no such early return, so this checks it neither crashes on
    `[user, *user.groups]` nor answers True."""
    from abilian.core.extensions.login import AnonymousUser

    ensure_services_started(["security"])
    anonymous = AnonymousUser()

    assert can_manage(community1, anonymous) is False
    assert can_manage(community1, anonymous) == _the_old_body(community1, anonymous)


# --- the two records must not drift ------------------------------------------


def test_the_member_list_and_the_role_assignments_agree(
    community1: Community, db: SQLAlchemy, app: Application
) -> None:
    """`Membership` stays the member list; `RoleAssignment` is the projection
    the engine reads. If they disagree, the members page and the permission
    check tell different stories."""
    ensure_services_started(["security"])
    for i, role in enumerate(ROLES):
        user = User(email=f"user{i}@example.com", can_login=True)
        db.session.add(user)
        db.session.flush()
        community1.set_membership(user, role)
    db.session.flush()

    for membership in community1.memberships:
        recorded = security_service.get_roles(
            membership.user, community1, no_group_roles=True
        )
        assert membership.role in recorded, (
            f"{membership.user.email} is {membership.role} in the member list "
            f"and {recorded} to the engine"
        )


def test_a_demotion_reaches_both(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    ensure_services_started(["security"])
    community1.set_membership(outsider, MANAGER)
    db.session.flush()
    assert can_manage(community1, outsider)

    community1.set_membership(outsider, MEMBER)
    db.session.flush()

    assert community1.get_role(outsider) == MEMBER
    assert not can_manage(community1, outsider)
