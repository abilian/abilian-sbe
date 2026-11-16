# Copyright (c) 2012-2024, Abilian SAS

"""Existing communities keep the manager they had.

Dropping the creator clause from the predicate takes management away from
every creator who was never made a member -- which, before this, was all of
them. The backfill writes the grant the clause stood for, as a membership.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture

from abilian.cli.backfill import (
    backfill_community_roles,
    backfill_creator_memberships,
)
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, READER
from abilian.sbe.apps.communities.roles import clear_roles
from abilian.sbe.apps.communities.security import can_manage
from abilian.services import security_service
from abilian.services.security import MANAGE
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@fixture
def creator(db: SQLAlchemy) -> User:
    user = User(email="creator@example.com", can_login=True)
    db.session.add(user)
    db.session.flush()
    return user


def _run(app: Application, *args: str) -> None:
    result = app.test_cli_runner().invoke(backfill_creator_memberships, args)
    assert result.exit_code == 0, result.output


def _run_roles(app: Application, *args: str) -> str:
    result = app.test_cli_runner().invoke(backfill_community_roles, args)
    assert result.exit_code == 0, result.output
    return result.output


def _as_before_the_signal(community: Community) -> None:
    """Remove every membership's role on the community itself, leaving the
    memberships and their folder projection: the state production data is in."""
    for membership in community.memberships:
        clear_roles(membership.user, community)


def test_a_creator_who_is_not_a_member_becomes_a_manager(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    ensure_services_started(["security"])
    community1.creator = creator
    db.session.commit()
    assert not can_manage(creator, community1), "the state the backfill is for"

    _run(app)

    db.session.expire_all()
    assert community1.get_role(creator) == MANAGER
    assert can_manage(creator, community1)


def test_a_role_someone_chose_is_not_overwritten(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    """Somebody may have demoted the creator on purpose. A backfill that
    silently promotes them back is a backfill that re-grants revoked access."""
    ensure_services_started(["security"])
    community1.creator = creator
    community1.set_membership(creator, READER)
    db.session.commit()

    _run(app)

    db.session.expire_all()
    assert community1.get_role(creator) == READER


def test_dry_run_writes_nothing(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    ensure_services_started(["security"])
    community1.creator = creator
    db.session.commit()

    _run(app, "--dry-run")

    db.session.expire_all()
    assert community1.get_role(creator) is None


# --- recording existing memberships on their community -----------------------


def test_an_existing_membership_becomes_a_role_on_its_community(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    """A membership written before the signal handler existed left the
    community unanswerable: `has_permission(user, MANAGE, community)` was False
    for its own manager."""
    ensure_services_started(["security"])
    community1.set_membership(creator, MANAGER)
    db.session.commit()
    _as_before_the_signal(community1)
    db.session.commit()
    assert not security_service.has_permission(creator, MANAGE, community1)

    _run_roles(app)

    db.session.expire_all()
    assert security_service.has_permission(creator, MANAGE, community1)


def test_it_is_idempotent(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    ensure_services_started(["security"])
    community1.set_membership(creator, MANAGER)
    db.session.commit()

    output = _run_roles(app)

    assert "0 memberships" in output, (
        f"the signal already recorded it, so there is nothing to do: {output!r}"
    )
    assert security_service.has_permission(creator, MANAGE, community1)


def test_dry_run_of_roles_writes_nothing(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    ensure_services_started(["security"])
    community1.set_membership(creator, MANAGER)
    db.session.commit()
    _as_before_the_signal(community1)
    db.session.commit()

    output = _run_roles(app, "--dry-run")

    db.session.expire_all()
    assert "2 memberships" in output, output
    assert not security_service.has_permission(creator, MANAGE, community1)


def test_a_second_run_finds_nothing_left(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    ensure_services_started(["security"])
    community1.set_membership(creator, MANAGER)
    db.session.commit()
    _as_before_the_signal(community1)
    db.session.commit()

    assert "2 memberships" in _run_roles(app)
    db.session.expire_all()
    assert "0 memberships" in _run_roles(app)


def test_a_reader_is_recorded_as_a_reader_and_nothing_more(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    ensure_services_started(["security"])
    reader = community1.test_user
    _as_before_the_signal(community1)
    db.session.commit()

    _run_roles(app)

    db.session.expire_all()
    assert security_service.get_roles(reader, community1, no_group_roles=True) == [
        READER
    ]
    assert not security_service.has_permission(reader, MANAGE, community1)


def test_the_upgrade_steps_in_the_order_the_changelog_gives(
    app: Application, db: SQLAlchemy, community1: Community, creator: User
) -> None:
    """Production data has both gaps at once: managers recorded only on the
    folder, and creators who were never members. After both backfills, run as
    `CHANGELOG.md` says, everyone who managed the community still does."""
    ensure_services_started(["security"])
    manager = User(email="manager@example.com", can_login=True)
    db.session.add(manager)
    community1.set_membership(manager, MANAGER)
    community1.creator = creator
    db.session.commit()
    _as_before_the_signal(community1)
    db.session.commit()
    assert not can_manage(manager, community1)
    assert not can_manage(creator, community1)

    _run_roles(app)
    _run(app)

    db.session.expire_all()
    assert can_manage(manager, community1)
    assert can_manage(creator, community1)
    assert not can_manage(community1.test_user, community1)
