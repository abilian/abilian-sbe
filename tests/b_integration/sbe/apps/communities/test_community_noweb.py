# Copyright (c) 2012-2024, Abilian SAS

"""Tests from test_community are currently refactored using pytest in this
module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

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
    from sqlalchemy.orm import Session

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy

# from .. import signals, views
# from ..models import MEMBER, READER, Community, CommunityIdColumn, community_content


@pytest.fixture
def community(db_session: Session) -> Community:
    community = Community(name="My Community")
    db_session.add(community)
    db_session.commit()
    return community


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

    # if community.folder was not deleted, this will raise IntegrityError. Test
    # passes if no exceptions is raised
    db.session.commit()


def test_rename(community: Community) -> None:
    NEW_NAME = "My new name"
    community.rename(NEW_NAME)
    assert community.name == NEW_NAME
    assert community.folder.name == NEW_NAME


def test_auto_slug(community: Community) -> None:
    assert community.slug == "my-community"


def test_membership(community: Community, db: SQLAlchemy) -> None:
    user = User(email="user@example.com")

    memberships = community.memberships
    assert memberships == []

    # setup signals testers with mocks.
    when_set = mock.MagicMock()
    when_set.mock_add_spec(["__name__"])  # required for signals
    signals.membership_set.connect(when_set)
    when_removed = mock.MagicMock()
    when_removed.mock_add_spec(["__name__"])
    signals.membership_removed.connect(when_removed)

    # invalid role
    with pytest.raises(ValueError, match="Invalid role"):
        community.set_membership(user, "dummy role name")

    assert not when_set.called
    assert not when_removed.called

    # simple member
    community.set_membership(user, MEMBER)
    db.session.commit()

    memberships = community.memberships
    assert len(memberships) == 1
    assert memberships[0].user == user
    assert memberships[0].role is MEMBER

    when_set.assert_called_once_with(community, is_new=True, membership=memberships[0])
    assert not when_removed.called
    when_set.reset_mock()

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

    when_set.assert_called_once_with(community, is_new=False, membership=memberships[0])
    assert not when_removed.called
    when_set.reset_mock()

    # remove user
    membership = memberships[0]
    community.remove_membership(user)
    db.session.commit()

    memberships = community.memberships
    assert memberships == []

    assert not when_set.called
    when_removed.assert_called_once_with(community, membership=membership)


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
    @community_content
    class CommunityContent(Entity):
        community_id = CommunityIdColumn()
        community = sa.orm.relationship(Community, foreign_keys=[community_id])

    sa.orm.configure_mappers()
    conn = db.session.connection()
    for table in sa.inspect(CommunityContent).tables:
        if not table.exists(conn):
            table.create(conn)

    cc = CommunityContent(name="my content", community=community)
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
        res = index_service.search("community", object_types=obj_types)
        assert len(res) == 0

    with login(user):
        res = index_service.search("community", object_types=obj_types)
        assert len(res) == 1
        hit = res[0]
        assert hit["object_key"] == community1.object_key

    with login(user_c2):
        res = index_service.search("community", object_types=obj_types)
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
        hit = index_service.search("community", object_types=obj_types)[0]
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
