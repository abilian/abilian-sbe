from __future__ import absolute_import, print_function, unicode_literals

from abilian.core.models.subjects import User
from pytest import fixture

from ..models import READER, Community


@fixture
def community(db):
    community = Community(name="My Community")
    db.session.add(community)
    db.session.flush()
    return community


@fixture
def community1(db):
    community = Community(name="My Community")
    db.session.add(community)

    user = User(
        email='user_1@example.com',
        password='azerty',
        can_login=True,
    )
    db.session.add(user)
    community.set_membership(user, READER)
    community.test_user = user

    db.session.flush()
    return community


@fixture
def community2(db):
    community = Community(name="Another Community")
    db.session.add(community)

    user = User(
        email='user_2@example.com',
        password='azerty',
        can_login=True,
    )
    db.session.add(user)
    community.set_membership(user, READER)
    community.test_user = user

    db.session.flush()
    return community
