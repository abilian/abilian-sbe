# Copyright (c) 2012-2026, Abilian SAS

"""A community's URL reaches its own objects, and no other community's.

The blueprint lets a member of one community in; the object in the URL is named
by its number, and nothing checked that it was that community's. A member of one
community read, and replied to, another's discussions, read and changed its
events, and changed its wiki pages, by changing a number in the address.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.models import MEMBER
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.web.util import url_for
from tests.forum_util import started_thread
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@pytest.fixture
def member(community1: Community, db: SQLAlchemy) -> User:
    """A member of the first community, and of no other."""
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MEMBER)
    db.session.commit()
    return community1.test_user


def _get(client: FlaskClient, user: User, endpoint: str, **kw) -> int:
    with client_login(client, user):
        return client.get(url_for(endpoint, **kw)).status_code


def test_another_communitys_thread_is_not_found_here(
    db: SQLAlchemy,
    client: FlaskClient,
    community1: Community,
    community2: Community,
    member: User,
) -> None:
    thread = started_thread(db, community2, community2.test_user, "Theirs", 1)
    here = {"community_id": community1.slug, "thread_id": thread.id}

    assert _get(client, member, "forum.thread", **here) == 404
    with client_login(client, member):
        reply = client.post(
            url_for("forum.thread_post", **here),
            data={"message": "<p>Mine.</p>", "__action": "create"},
        )
    assert reply.status_code == 404
    db.session.expire_all()
    assert len(thread.posts) == 2


def test_another_communitys_event_is_not_found_here(
    db: SQLAlchemy,
    client: FlaskClient,
    community1: Community,
    community2: Community,
    member: User,
) -> None:
    start = datetime.now() + timedelta(days=3)
    event = Event(title="Theirs", community=community2, start=start)
    db.session.add(event)
    db.session.commit()
    here = {"community_id": community1.slug, "event_id": event.id}

    for endpoint in ("calendar.event", "calendar.event_edit"):
        assert _get(client, member, endpoint, **here) == 404, endpoint


def test_another_communitys_wiki_page_is_not_changed_from_here(
    db: SQLAlchemy,
    client: FlaskClient,
    community1: Community,
    community2: Community,
    member: User,
) -> None:
    page = WikiPage(title="Theirs", body_src="Their text.")
    page.community_id = community2.id
    db.session.add(page)
    db.session.commit()

    with client_login(client, member):
        response = client.post(
            url_for("wiki.page_edit", community_id=community1.slug),
            data={
                "title": "Theirs",
                "page_id": page.id,
                "body_src": "Mine now.",
                "__action": "edit",
            },
        )

    assert response.status_code == 404
    db.session.expire_all()
    assert db.session.get(WikiPage, page.id).body_src == "Their text."
