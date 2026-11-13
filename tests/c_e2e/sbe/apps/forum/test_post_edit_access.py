# Copyright (c) 2012-2024, Abilian SAS

"""Who may edit a forum post.

`thread.html` offers the Edit link to the post's author or a site admin.
`ThreadPostEdit` enforced nothing at all: the community blueprint's
`check_membership` gates the route to members of the community, and nothing
below that asked whose post it was. So any member could edit any other
member's post by following the URL the template declines to show them --
putting words in someone else's mouth, which is worse than the moderation
actions a manager legitimately has.

Deliberately *not* extended to community managers. Closing or deleting a
thread is moderation and belongs to whoever runs the community (`7e0cb0d`);
rewriting somebody's message is not the same act, and the UI has never
offered it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for
from pytest import fixture

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.forum.models import Thread
from abilian.services import security_service
from abilian.services.security import ADMIN
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _member(db: SQLAlchemy, community: Community, email: str, role=MEMBER) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.flush()
    return user


@fixture
def author(db: SQLAlchemy, community1: Community) -> User:
    ensure_services_started(["security"])
    return _member(db, community1, "author@example.com")


@fixture
def thread_and_post(db: SQLAlchemy, community1: Community, author: User):
    thread = Thread(title="A conversation", community=community1)
    thread.creator = thread.owner = author
    post = thread.create_post(body_html="<p>my words</p>")
    post.creator = post.owner = author
    db.session.add(thread)
    db.session.commit()
    return thread, post


def _edit_url(community: Community, thread, post) -> str:
    return url_for(
        "forum.post_edit",
        community_id=community.slug,
        thread_id=thread.id,
        object_id=post.id,
    )


def test_another_member_cannot_edit_your_post(
    community1: Community,
    thread_and_post,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """The escalation: the link is hidden from them, the route was not."""
    thread, post = thread_and_post
    other = _member(db, community1, "other@example.com")
    db.session.commit()

    with client_login(client, other):
        response = client.get(_edit_url(community1, thread, post))

    assert response.status_code == 403


def test_a_community_manager_cannot_either(
    community1: Community,
    thread_and_post,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """Moderation is closing and deleting, not rewriting."""
    thread, post = thread_and_post
    manager = _member(db, community1, "manager@example.com", MANAGER)
    db.session.commit()

    with client_login(client, manager):
        response = client.get(_edit_url(community1, thread, post))

    assert response.status_code == 403


def test_the_author_can(
    community1: Community,
    thread_and_post,
    author: User,
    client: FlaskClient,
    app: Application,
) -> None:
    thread, post = thread_and_post

    with client_login(client, author):
        response = client.get(_edit_url(community1, thread, post))

    assert response.status_code == 200


def test_a_site_admin_can(
    community1: Community,
    thread_and_post,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """What the template already offers them."""
    thread, post = thread_and_post
    admin = _member(db, community1, "admin@example.com")
    security_service.grant_role(admin, ADMIN)
    db.session.commit()

    with client_login(client, admin):
        response = client.get(_edit_url(community1, thread, post))

    assert response.status_code == 200
