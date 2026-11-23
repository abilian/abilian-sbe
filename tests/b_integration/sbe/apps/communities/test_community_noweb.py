# Copyright (c) 2012-2024, Abilian SAS

"""Tests from test_community are currently refactored using pytest in this
module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

from abilian.core.entities import Entity
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities import signals, views
from abilian.sbe.apps.communities.models import (
    MEMBER,
    READER,
    Community,
    CommunityIdColumn,
    community_content,
)
from abilian.sbe.apps.documents.models import Folder
from abilian.sbe.apps.documents.repository import content_repository
from abilian.services import index_service, security_service
from tests.util import login

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


@community_content
class DecoratedContent(Entity):
    """Content of a community, as `community_content` makes it.

    Defined once, here: a mapped class defined in a test is added to the
    metadata every test shares, again each time the test runs.
    """

    community_id = CommunityIdColumn()
    community = sa.orm.relationship(Community, foreign_keys=[community_id])


@pytest.fixture
def community(db_session: Session) -> Community:
    community = Community(name="My Community")
    db_session.add(community)
    db_session.commit()
    return community


@pytest.fixture
def membership_signals() -> Iterator[dict[str, list]]:
    """The membership signals sent during the test, by name."""
    received: dict[str, list] = {"set": [], "removed": []}

    def on_set(sender: Community, **kwargs: object) -> None:
        received["set"].append((sender, kwargs))

    def on_removed(sender: Community, **kwargs: object) -> None:
        received["removed"].append((sender, kwargs))

    signals.membership_set.connect(on_set)
    signals.membership_removed.connect(on_removed)
    yield received
    signals.membership_set.disconnect(on_set)
    signals.membership_removed.disconnect(on_removed)


#
# Actual tests
#
def test_instanciation(db: SQLAlchemy) -> None:
    community = Community(name="My Community")
    assert isinstance(community.folder, Folder)
    # assert isinstance(community.group, Group)


def test_default_view_kw() -> None:
    # test exceptions are handled if passed an object with 'community' attribute
    # and no community_id in kwargs. and ValueError is properly raised
    dummy = type("Dummy", (object,), {"community": None})()

    with pytest.raises(ValueError, match="Cannot find community_id value"):
        views.default_view_kw({}, dummy, "dummy", 1)


def test_default_url(app: Application, community: Community) -> None:
    url = app.default_view.url_for(community)
    assert url.endswith("/communities/my-community/")


def test_can_recreate_with_same_name(community: Community, db: SQLAlchemy) -> None:
    name = community.name

    db.session.delete(community)
    db.session.commit()

    community = Community(name=name)
    db.session.add(community)
    # Raises IntegrityError if the first community's folder was left behind.
    db.session.commit()
    db.session.expire_all()

    assert Community.query.one().name == name
    assert community.folder.name == name


def test_rename(community: Community) -> None:
    NEW_NAME = "My new name"
    community.rename(NEW_NAME)
    assert community.name == NEW_NAME
    assert community.folder.name == NEW_NAME


def test_auto_slug(community: Community) -> None:
    assert community.slug == "my-community"


def test_membership(
    community: Community, db: SQLAlchemy, membership_signals: dict[str, list]
) -> None:
    user = User(email="user@example.com")

    memberships = community.memberships
    assert memberships == []

    # invalid role
    with pytest.raises(ValueError, match="Invalid role"):
        community.set_membership(user, "dummy role name")

    assert membership_signals == {"set": [], "removed": []}

    # simple member
    community.set_membership(user, MEMBER)
    db.session.commit()

    memberships = community.memberships
    assert len(memberships) == 1
    assert memberships[0].user == user
    assert memberships[0].role is MEMBER

    assert membership_signals == {
        "set": [(community, {"is_new": True, "membership": memberships[0]})],
        "removed": [],
    }
    membership_signals["set"].clear()

    assert community.get_role(user) is MEMBER

    assert community.get_memberships() == [memberships[0]]
    assert community.get_memberships("member") == [memberships[0]]
    assert community.get_memberships("manager") == []

    # change user role
    community.set_membership(user, "manager")
    db.session.commit()

    memberships = community.memberships
    assert len(memberships) == 1
    assert memberships[0].user == user
    assert memberships[0].role == "manager"

    assert community.get_role(user) == "manager"

    assert membership_signals == {
        "set": [(community, {"is_new": False, "membership": memberships[0]})],
        "removed": [],
    }
    membership_signals["set"].clear()

    # remove user
    membership = memberships[0]
    community.remove_membership(user)
    db.session.commit()

    memberships = community.memberships
    assert memberships == []

    assert membership_signals == {
        "set": [],
        "removed": [(community, {"membership": membership})],
    }


def test_folder_roles(community: Community, db: SQLAlchemy, app: Application) -> None:
    user = User(email="user@example.com")
    folder = community.folder
    community.set_membership(user, MEMBER)
    db.session.commit()

    assert security_service.get_roles(user, folder) == ["reader"]

    # this tests a bug, where local roles whould disappear when setting
    # membership twice
    community.set_membership(user, MEMBER)
    assert security_service.get_roles(user, folder) == ["reader"]


def test_community_content_decorator(community: Community, db: SQLAlchemy) -> None:
    cc = DecoratedContent(name="my content", community=community)
    db.session.add(cc)
    db.session.flush()
    assert hasattr(cc, "community_slug")
    assert cc.community_slug == "my-community"
    assert cc.slug == "my-content"


##########################################################################


def test_community_indexed(app: Application, db: SQLAlchemy, monkeypatch) -> None:
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    index_service.start()

    security_service.start()

    obj_types = (Community.entity_type,)

    user_no_community = User(email="no_community@example.com")
    db.session.add(user_no_community)

    community1 = Community(name="My Community")
    db.session.add(community1)

    community2 = Community(name="Other community")
    db.session.add(community2)

    user = User(email="user_1@example.com")
    db.session.add(user)
    community1.set_membership(user, READER)

    user_c2 = User(email="user_2@example.com")
    db.session.add(user_c2)
    community2.set_membership(user_c2, READER)

    db.session.commit()

    with login(user_no_community):
        res = index_service.search(
            "community", object_types=obj_types, user=user_no_community
        )
        assert len(res) == 0

    with login(user):
        res = index_service.search("community", object_types=obj_types, user=user)
        assert len(res) == 1
        hit = res[0]
        assert hit["object_key"] == community1.object_key

    with login(user_c2):
        res = index_service.search("community", object_types=obj_types, user=user_c2)
        assert len(res) == 1
        hit = res[0]
        assert hit["object_key"] == community2.object_key


def test_default_view_kw_with_hit(
    app: Application, db: SQLAlchemy, community: Community, monkeypatch
) -> None:
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    index_service.start()

    security_service.start()

    user = User(email="user_1@example.com")
    db.session.add(user)
    community.set_membership(user, READER)

    obj_types = (Community.entity_type,)

    with login(user):
        hit = index_service.search("community", object_types=obj_types, user=user)[0]
        kw = views.default_view_kw({}, hit, hit["object_type"], hit["id"])
        assert kw == {"community_id": community.slug}


def test_membership_repr(community: Community, db: SQLAlchemy) -> None:
    user = User(email="user@example.com")
    community.set_membership(user, MEMBER)
    db.session.flush()
    membership = community.memberships[0]

    assert repr(membership).startswith("<Membership user=")


def test_a_new_community_folder_is_under_the_root(db: SQLAlchemy) -> None:
    root = content_repository.root_folder
    db.session.add(root)
    db.session.commit()

    community = Community(name="Rooted")
    db.session.add(community)
    db.session.commit()
    db.session.expire_all()

    assert community.folder.parent == content_repository.root_folder
    assert community.folder in content_repository.root_folder.subfolders


def test_the_first_community_saves_the_root_folder(db: SQLAlchemy) -> None:
    assert Folder.query.count() == 0

    community = Community(name="First")
    db.session.add(community)
    db.session.commit()
    db.session.expire_all()

    root = content_repository.root_folder
    assert root.id is not None
    assert community.folder.parent == root
