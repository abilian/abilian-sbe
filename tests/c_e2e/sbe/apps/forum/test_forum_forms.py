# Copyright (c) 2012-2026, Abilian SAS

"""The forum's forms on the Abilian Design System: starting a discussion, and editing
a message with its files.

Who may edit a message is in `test_post_edit_access.py`; the editor and the uploader
in a browser, in `e2e_playwright/test_forms.py`.
"""

from __future__ import annotations

from html import unescape
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from abilian.sbe.apps.communities.models import MEMBER
from abilian.sbe.apps.forum.models import PostAttachment, Thread
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community
    from abilian.sbe.apps.forum.models import Post


@pytest.fixture
def member(community1: Community, db: SQLAlchemy) -> User:
    """A member of a community that is not participative: they may not send by
    email."""
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MEMBER)
    db.session.commit()
    return community1.test_user


@pytest.fixture
def post(community1: Community, member: User, db: SQLAlchemy) -> Post:
    """The member's message, with the minutes attached."""
    thread = Thread(title="The general meeting", community=community1)
    thread.creator = thread.owner = member
    post = thread.create_post(body_html="<p>The minutes.</p>")
    post.creator = post.owner = member
    attachment = PostAttachment(name="minutes.txt", post=post)
    attachment.set_content(b"Approved.", "text/plain")
    db.session.add_all([thread, attachment])
    db.session.commit()
    return post


def _new_thread(community: Community) -> str:
    return url_for("forum.new_thread", community_id=community.slug)


def _edit(post: Post) -> str:
    return url_for(
        "forum.post_edit",
        community_id=post.thread.community.slug,
        thread_id=post.thread.id,
        object_id=post.id,
    )


def test_a_new_discussion_says_where_it_goes(
    community1: Community, member: User, client: FlaskClient
) -> None:
    with client_login(client, member):
        response = client.get(_new_thread(community1))

    html = unescape(response.get_data(as_text=True))
    assert response.status_code == 200
    assert 'name="title"' in html
    assert "data-richtext" in html
    assert "Seen by the community's only member." in html
    assert 'name="send_by_email"' not in html


def test_a_discussion_without_a_subject_comes_back_with_the_error(
    community1: Community, member: User, client: FlaskClient
) -> None:
    data = {"title": "", "message": "<p>Hello.</p>", "__action": "create"}
    with client_login(client, member):
        response = client.post(_new_thread(community1), data=data)

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    subject = html.split('name="title"')[1].split(">")[0]
    assert 'aria-invalid="true"' in subject
    assert 'class="ads-error" id="title-error"' in html
    assert Thread.query.count() == 0


def test_editing_a_message_lists_its_files_and_removes_one(
    post: Post, member: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    data = {
        "message": "<p>The minutes, approved.</p>",
        "__attachments_delete__": "0",
        "reason": "Approved",
        "__action": "edit",
    }
    with client_login(client, member):
        page = unescape(client.get(_edit(post)).get_data(as_text=True))
        response = client.post(_edit(post), data=data)

    assert "minutes.txt" in page
    assert 'aria-label="Remove minutes.txt"' in page
    assert response.status_code == 302
    db.session.expire_all()
    assert post.body_html == "<p>The minutes, approved.</p>"
    assert post.attachments == []


@pytest.mark.parametrize("index", ["1", "-1"])
def test_a_removal_index_naming_no_file_of_the_message_removes_none(
    index: str, post: Post, member: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    # The message has one file, numbered 0: 1 is past it, -1 would be the last.
    data = {
        "message": "<p>The minutes.</p>",
        "__attachments_delete__": index,
        "__action": "edit",
    }
    with client_login(client, member):
        response = client.post(_edit(post), data=data)

    assert response.status_code == 302
    db.session.expire_all()
    assert [a.name for a in post.attachments] == ["minutes.txt"]


def test_a_file_uploaded_for_the_edit_is_attached_to_the_message(
    app: Application,
    post: Post,
    member: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    uploads = app.extensions["uploads"]
    handle = uploads.add_file(
        member, BytesIO(b"Signed."), filename="signed.txt", mimetype="text/plain"
    )
    data = {
        "message": "<p>The minutes, signed.</p>",
        "attachments": handle,
        "__action": "edit",
    }
    with client_login(client, member):
        response = client.post(_edit(post), data=data)

    assert response.status_code == 302
    db.session.expire_all()
    assert sorted(a.name for a in post.attachments) == ["minutes.txt", "signed.txt"]


def test_a_message_under_another_threads_url_is_not_found(
    community1: Community,
    post: Post,
    member: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    other = Thread(title="Another", community=community1)
    other.creator = other.owner = member
    other.create_post(body_html="<p>Else.</p>")
    db.session.add(other)
    db.session.commit()
    url = url_for(
        "forum.post_edit",
        community_id=community1.slug,
        thread_id=other.id,
        object_id=post.id,
    )

    with client_login(client, member):
        response = client.get(url)

    assert response.status_code == 404


def test_an_action_the_form_does_not_offer_is_a_bad_request(
    post: Post, member: User, client: FlaskClient
) -> None:
    data = {"message": "<p>The minutes.</p>", "__action": "frobnicate"}
    with client_login(client, member):
        response = client.post(_edit(post), data=data)

    assert response.status_code == 400
