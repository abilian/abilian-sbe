# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.core.models.subjects import BcryptPasswordStrategy, Group, User

if TYPE_CHECKING:
    from flask import Flask

    from abilian.core.sqlalchemy import SQLAlchemy


def test_non_ascii_password() -> None:
    """Ensure we can store and test non-ascii password without any
    UnicodeEncodeError."""
    user = User()

    user.set_password("Hé")

    if not isinstance(user.password, str):
        # when actually retrieved from database, it should be Unicode
        user.password = str(user.password)

    assert user.authenticate("Hé")


def test_a_user_without_password_cannot_log_in() -> None:
    # Bcrypt itself: the tests otherwise store passwords in clear.
    user = User()
    user.password = None

    assert not BcryptPasswordStrategy().authenticate(user, "anything")


def test_user(app: Flask, db: SQLAlchemy) -> None:
    user = User(email="test@test.com")
    db.session.add(user)
    db.session.flush()

    assert not user.is_online


def test_group(app: Flask, db: SQLAlchemy) -> None:
    group = Group(name="test_group")
    db.session.add(group)
    db.session.flush()

    assert group.members_count == 0


def test_follow(app: Flask, db: SQLAlchemy) -> None:
    user1 = User(email="test1@test.com")
    user2 = User(email="test2@test.com")
    db.session.add(user1)
    db.session.add(user2)
    db.session.flush()

    assert not user1.is_following(user2)

    user1.follow(user2)
    assert user1.is_following(user2)

    user1.unfollow(user2)
    assert not user1.is_following(user2)


def test_group_membership(app: Flask, db: SQLAlchemy) -> None:
    user = User(email="test@test.com")
    db.session.add(user)
    group = Group(name="test_group")
    db.session.add(group)
    db.session.flush()

    assert not user.is_member_of(group)

    user.join(group)
    assert user.is_member_of(group)
    assert user in group.members

    user.leave(group)
    assert not user.is_member_of(group)
