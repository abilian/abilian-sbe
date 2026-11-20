# Copyright (c) 2012-2024, Abilian SAS

"""Who may manage a community.

The rule used to be written out three times -- in `Community.has_permission`,
in `is_manager` and in the route guard -- each with its own admin check, and
one of them with an extra grant the others did not have. Nothing pinned any of
them down. `can_manage` is now the only place that knows it, so this is where
it gets pinned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MEMBER
from abilian.sbe.apps.communities.presenters import CommunityPresenter
from abilian.sbe.apps.communities.security import can_manage, is_member
from abilian.services import security_service
from abilian.services.security import (
    ADMIN,
    MANAGE,
    MANAGER,
    READ,
    READER,
    WRITE,
    WRITER,
)

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@pytest.fixture
def outsider(db: SQLAlchemy) -> User:
    user = User(email="outsider@example.com", can_login=True)
    db.session.add(user)
    db.session.flush()
    return user


def test_a_manager_can_manage(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    security_service.start()
    community1.set_membership(outsider, MANAGER)
    db.session.flush()

    assert can_manage(outsider, community1)


@pytest.mark.parametrize("role", [READER, MEMBER])
def test_lesser_roles_cannot_manage(
    role, community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """Notably MEMBER, which the old table granted read and write to."""
    security_service.start()
    community1.set_membership(outsider, role)
    db.session.flush()

    assert not can_manage(outsider, community1)


def test_a_non_member_cannot_manage(
    community1: Community, outsider: User, app: Application
) -> None:
    security_service.start()

    assert not can_manage(outsider, community1)


def test_a_site_admin_can_manage_any_community(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    security_service.start()
    security_service.grant_role(outsider, ADMIN)
    db.session.flush()

    assert can_manage(outsider, community1)


def test_a_site_admin_passes_even_with_no_community(
    db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """The route guard fell through to a bare admin check when g.community was
    unset. Keep that: an admin must not start getting 403s on those views."""
    security_service.start()
    security_service.grant_role(outsider, ADMIN)
    db.session.flush()

    assert can_manage(outsider, None)


def test_the_model_method_delegates(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    security_service.start()
    community1.set_membership(outsider, MANAGER)
    db.session.flush()

    assert community1.has_permission(outsider, MANAGE) == can_manage(
        outsider, community1
    )


def test_the_model_method_answers_every_permission_now(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """It used to raise for anything but MANAGE: community roles lived in
    `Membership`, where the engine could not see them. They are recorded on the
    community itself now, so this is a plain delegate."""
    security_service.start()
    community1.set_membership(outsider, MANAGER)
    db.session.flush()

    assert community1.has_permission(outsider, READ)
    assert community1.has_permission(outsider, WRITE)
    assert community1.has_permission(outsider, MANAGE)


def test_a_plain_member_holds_no_permission_on_the_community(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """MEMBER is in no entry of the engine's default permission matrix, so a
    membership on its own confers nothing at the community level. Access to a
    community's *content* comes from the folder projection, which maps MEMBER
    to READER or WRITER by community type."""
    security_service.start()
    community1.set_membership(outsider, MEMBER)
    db.session.flush()

    assert not community1.has_permission(outsider, READ)
    assert not community1.has_permission(outsider, MANAGE)
    assert security_service.has_permission(outsider, READ, community1.folder)


def test_a_presenter_is_accepted_where_a_community_is(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """`g.community` is a `CommunityPresenter`, so this is what the views pass.

    It forwards every attribute, which is why the old role-reading body never
    noticed -- but `has_role` asserts its object is an `Entity`, and a
    presenter is not one however well it forwards.
    """
    security_service.start()
    community1.set_membership(outsider, MANAGER)
    db.session.flush()

    assert can_manage(outsider, CommunityPresenter(community1))


def test_being_the_creator_grants_nothing_by_itself(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """The mismatch this consolidation exposed, now reconciled the other way.

    `is_manager` used to grant to `community.creator` while `can_manage` --
    what the `@can_manage` route guard enforces -- did not, so a creator who was not a
    manager was offered the manage actions and refused by the views behind
    them. Creators are made MANAGER members at creation instead (see
    `tests/c_e2e/.../test_community_create.py`), which is a membership anyone
    can see in the member list and revoke there.

    So the attribute on its own says nothing about who manages.
    """
    security_service.start()
    community1.creator = outsider
    db.session.flush()

    assert not can_manage(outsider, community1)


# --- is_member: what `has_access` became --------------------------------------


def test_every_membership_role_counts_as_membership(
    community1: Community, db: SQLAlchemy, app: Application
) -> None:
    """MANAGER, MEMBER, READER and WRITER all mean "is in this community",
    which is why `is_member` asks `has_role` with the set rather than naming
    one role."""
    security_service.start()
    for i, role in enumerate([MANAGER, MEMBER, READER, WRITER]):
        user = User(email=f"m{i}@example.com", can_login=True)
        db.session.add(user)
        db.session.flush()
        community1.set_membership(user, role)
        db.session.flush()

        assert is_member(user, community1), role


def test_an_outsider_is_not_a_member(
    community1: Community, outsider: User, app: Application
) -> None:
    security_service.start()

    assert not is_member(outsider, community1)


def test_a_site_admin_passes_without_being_a_member(
    community1: Community, db: SQLAlchemy, outsider: User, app: Application
) -> None:
    """`has_role` seeds its valid roles with ADMIN and MANAGER, so this comes
    for free where `has_access` needed a clause of its own."""
    security_service.start()
    security_service.grant_role(outsider, ADMIN)
    db.session.flush()

    assert is_member(outsider, community1)


def test_an_anonymous_user_is_not_a_member(
    community1: Community, app: Application
) -> None:
    from abilian.core.extensions.login import AnonymousUser

    security_service.start()

    assert not is_member(AnonymousUser(), community1)
