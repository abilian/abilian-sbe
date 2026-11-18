# Copyright (c) 2026, Abilian SAS

"""A community's discussions by month, the files attached to them, and all of the
community's files."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING

import pytest

from abilian.sbe.apps.communities.models import MEMBER
from abilian.sbe.apps.forum.models import PostAttachment, Thread
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@pytest.fixture
def member(community1: Community, db: SQLAlchemy) -> User:
    """A member who started a discussion, the minutes attached to its message."""
    # The community's files come from the search index as well as from the forum.
    ensure_services_started(["security", "indexing"])
    member = community1.test_user
    community1.set_membership(member, MEMBER)
    thread = Thread(title="The general meeting", community=community1)
    thread.creator = thread.owner = member
    post = thread.create_post(body_html="<p>The minutes.</p>")
    post.creator = post.owner = member
    attachment = PostAttachment(name="minutes.txt", post=post)
    attachment.set_content(b"Approved.", "text/plain")
    db.session.add_all([thread, attachment])
    db.session.commit()
    return member


def _page(client: FlaskClient, user: User, endpoint: str, community: Community) -> str:
    with client_login(client, user):
        response = client.get(url_for(endpoint, community_id=community.slug))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


@pytest.mark.parametrize(
    ("endpoint", "pill"),
    [("forum.archives", "By month"), ("forum.attachments", "Attachments")],
)
def test_each_view_of_the_discussions_is_its_pill(
    endpoint: str, pill: str, client: FlaskClient, community1: Community, member: User
) -> None:
    html = _page(client, member, endpoint, community1)

    assert f'aria-current="page">{pill}</a>' in html


def test_the_discussions_by_month(
    client: FlaskClient, community1: Community, member: User
) -> None:
    html = _page(client, member, "forum.archives", community1)

    assert "The general meeting" in html


def test_the_attachments_say_where_they_were_posted(
    client: FlaskClient, community1: Community, member: User
) -> None:
    html = _page(client, member, "forum.attachments", community1)

    assert "minutes.txt" in html
    assert "in <a" in html
    assert "The general meeting</a>" in html


def test_all_the_files_include_the_discussions(
    client: FlaskClient, community1: Community, member: User
) -> None:
    html = _page(client, member, "wall.files", community1)

    assert "minutes.txt" in html
