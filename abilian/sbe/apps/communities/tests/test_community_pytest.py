# coding=utf-8
"""
Tests from test_community are currently refactored using pytest in this module.
"""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

import pytest
import sqlalchemy as sa
from mock import mock
from pytest import fixture

from abilian.core.entities import Entity
from abilian.core.models.subjects import User
from abilian.sbe.apps.documents.models import Folder

from .. import signals, views
from ..models import MEMBER, Community, CommunityIdColumn, community_content


@fixture
def community(db):
    community = Community(name="My Community")
    db.session.add(community)
    db.session.commit()
    return community


#
# Actual tests
#
def test_instanciation(db):
    community = Community(name="My Community")
    assert isinstance(community.folder, Folder)
    # assert isinstance(community.group, Group)


def test_default_view_kw():
    # test exceptions are handled if passed an object with 'community' attribute
    # and no community_id in kwargs. and ValueError is properly raised
    dummy = type(b'Dummy', (object,), {b'community': None})()
    with pytest.raises(ValueError) as exc_info:
        views.default_view_kw({}, dummy, 'dummy', 1)

    assert exc_info.value.message == 'Cannot find community_id value'


def test_default_url(app, community):
    assert app.default_view.url_for(
        community) == 'http://localhost/communities/my-community/'


def test_can_recreate_with_same_name(community, db):
    name = community.name

    db.session.delete(community)
    db.session.commit()

    community = Community(name=name)
    db.session.add(community)

    # if community.folder was not deleted, this will raise IntegrityError. Test
    # passes if no exceptions is raised
    db.session.commit()


def test_rename(community):
    NEW_NAME = "My new name"
    community.rename(NEW_NAME)
    assert community.name == NEW_NAME
    assert community.folder.name == NEW_NAME


def test_auto_slug(community):
    assert community.slug == 'my-community'


def test_membership(community, db):
    user = User(email="user@example.com")

    l = community.memberships
    assert l == []

    # setup signals testers with mocks.
    when_set = mock.MagicMock()
    when_set.mock_add_spec(['__name__'])  # required for signals
    signals.membership_set.connect(when_set)
    when_removed = mock.MagicMock()
    when_removed.mock_add_spec(['__name__'])
    signals.membership_removed.connect(when_removed)

    # invalid role
    with pytest.raises(ValueError):
        community.set_membership(user, 'dummy role name')

    assert not when_set.called
    assert not when_removed.called

    # simple member
    community.set_membership(user, "member")
    db.session.commit()

    l = community.memberships
    assert len(l) == 1
    assert l[0].user == user
    assert l[0].role is MEMBER

    when_set.assert_called_once_with(community, is_new=True, membership=l[0])
    assert not when_removed.called
    when_set.reset_mock()

    assert community.get_role(user) is MEMBER

    assert community.get_memberships() == [l[0]]
    assert community.get_memberships('member') == [l[0]]
    assert community.get_memberships('manager') == []

    # change user role
    community.set_membership(user, "manager")
    db.session.commit()

    l = community.memberships
    assert len(l) == 1
    assert l[0].user == user
    assert l[0].role == "manager"

    assert community.get_role(user) == "manager"

    when_set.assert_called_once_with(community, is_new=False, membership=l[0])
    assert not when_removed.called
    when_set.reset_mock()

    # remove user
    membership = l[0]
    community.remove_membership(user)
    db.session.commit()

    l = community.memberships
    assert l == []

    assert not when_set.called
    when_removed.assert_called_once_with(community, membership=membership)


def test_folder_roles(community, db, app):
    user = User(email="user@example.com")
    folder = community.folder
    community.set_membership(user, "member")
    db.session.commit()
    security = app.services['security']

    assert security.get_roles(user, folder) == ["reader"]

    # this tests a bug, where local roles whould disappear when setting
    # membership twice
    community.set_membership(user, "member")
    assert security.get_roles(user, folder) == ["reader"]


def test_community_content_decorator(community, db):

    @community_content
    class CommunityContent(Entity):
        community_id = CommunityIdColumn()
        community = sa.orm.relation(Community, foreign_keys=[community_id])

    sa.orm.configure_mappers()
    conn = db.session.connection()
    for table in sa.inspect(CommunityContent).tables:
        if not table.exists(conn):
            table.create(conn)

    cc = CommunityContent(name='my content', community=community)
    db.session.add(cc)
    db.session.flush()
    assert hasattr(cc, 'community_slug')
    assert cc.community_slug == 'my-community'
    assert cc.slug == 'my-content'

    index_to = dict(CommunityContent.__indexation_args__['index_to'])
    assert 'community_slug' in index_to
