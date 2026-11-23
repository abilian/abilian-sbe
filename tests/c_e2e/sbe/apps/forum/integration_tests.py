# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import email
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest
from dramatiq import Message
from flask import url_for
from flask_login import login_user
from loguru import logger

from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.forum.models import Post, Thread
from abilian.sbe.apps.forum.tasks import (
    build_reply_email_address,
    extract_email_destination,
    process_email,
    send_post_by_email,
)
from abilian.services import get_service, security_service
from tests.forum_util import get_string_from_file, started_thread
from tests.util import client_login

if TYPE_CHECKING:
    from collections.abc import Iterator

    from dramatiq.brokers.stub import StubBroker
    from flask_sqlalchemy import SQLAlchemy

    from abilian.services.indexing.service import IndexService


def test_a_new_post_is_saved(db: SQLAlchemy, community1) -> None:
    thread = Thread(community=community1, title="saved")
    db.session.add(thread)
    db.session.flush()

    thread.create_post(body_html="hello")
    db.session.commit()

    assert Post.query.filter(Post.thread_id == thread.id).count() == 1


def test_posts_ordering(db: SQLAlchemy, community1) -> None:
    thread = Thread(community=community1, title="test ordering")
    db.session.add(thread)
    t1 = datetime(2014, 6, 20, 15, 0, 0)
    p1 = Post(thread=thread, body_html="post 1", created_at=t1)
    t2 = datetime(2014, 6, 20, 15, 1, 0)
    p2 = Post(thread=thread, body_html="post 2", created_at=t2)
    db.session.add_all([p1, p2])
    db.session.flush()
    p1_id, p2_id = p1.id, p2.id
    assert [p.id for p in thread.posts] == [p1_id, p2_id]

    # set post1 created after post2
    t1 += timedelta(minutes=2)
    p1.created_at = t1
    db.session.flush()
    db.session.expire(thread)  # force thread.posts refreshed from DB
    assert [p.id for p in thread.posts] == [p2_id, p1_id]


def test_thread_indexed(
    app, db: SQLAlchemy, community1, community2, monkeypatch
) -> None:
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    index_svc = cast("IndexService", get_service("indexing"))
    index_svc.start()
    security_service.start()

    thread1 = Thread(title="Community 1", community=community1)
    db.session.add(thread1)

    thread2 = Thread(title="Community 2: other", community=community2)
    db.session.add(thread2)
    db.session.commit()

    obj_types = (Thread.entity_type,)

    login_user(community1.test_user)
    res = index_svc.search(
        "community", object_types=obj_types, user=community1.test_user
    )
    assert len(res) == 1
    hit = res[0]
    assert hit["object_key"] == thread1.object_key

    login_user(community2.test_user)
    res = index_svc.search(
        "community", object_types=obj_types, user=community2.test_user
    )
    assert len(res) == 1
    hit = res[0]
    assert hit["object_key"] == thread2.object_key


def test_forum_home(client, community1, login_admin) -> None:
    response = client.get(url_for("forum.index", community_id=community1.slug))
    assert response.status_code == 200


@pytest.fixture
def broker(app) -> StubBroker:
    broker = send_post_by_email.broker
    broker.flush_all()
    return broker


def queued_mailings(broker: StubBroker) -> list[tuple]:
    """The posts queued to be mailed to the community's members."""
    queue = broker.queues[send_post_by_email.queue_name].queue
    messages = [Message.decode(data) for data in queue]
    return [m.args for m in messages if m.actor_name == send_post_by_email.actor_name]


@pytest.mark.parametrize(("role", "mailed"), [(MEMBER, False), (MANAGER, True)])
def test_only_a_manager_mails_a_new_thread_of_an_informative_community(
    db: SQLAlchemy, client, community1, broker: StubBroker, role, mailed: bool
) -> None:
    user = community1.test_user
    assert community1.type == "informative"
    community1.set_membership(user, role)
    db.session.commit()
    url = url_for("forum.new_thread", community_id=community1.slug)
    data = {
        "title": "Brand new thread",
        "message": "Shiny.",
        "__action": "create",
        "send_by_email": "y",
    }

    with client_login(client, user):
        response = client.post(url, data=data)

    assert response.status_code == 302
    post = Post.query.one()
    assert queued_mailings(broker) == ([(post.id,)] if mailed else [])


def test_a_thread_is_not_mailed_unless_asked(
    db: SQLAlchemy, client, community1, broker: StubBroker
) -> None:
    user = community1.test_user
    community1.set_membership(user, MANAGER)
    db.session.commit()
    url = url_for("forum.new_thread", community_id=community1.slug)
    data = {"title": "Brand new thread", "message": "Shiny.", "__action": "create"}

    with client_login(client, user):
        response = client.post(url, data=data)

    assert response.status_code == 302
    assert Post.query.count() == 1
    assert queued_mailings(broker) == []


def test_a_reply_is_shown_on_its_thread_and_mailed(
    db: SQLAlchemy, client, community1, broker: StubBroker
) -> None:
    user = community1.test_user
    community1.set_membership(user, MANAGER)
    db.session.commit()
    thread = started_thread(db, community1, user, "Budget 2027")
    url = url_for(
        "forum.thread_post", community_id=community1.slug, thread_id=thread.id
    )
    data = {"message": "My cherished post", "__action": "create", "send_by_email": "y"}

    with client_login(client, user):
        response = client.post(url, data=data)
        page = client.get(url).get_data(as_text=True)

    assert response.status_code == 302
    assert "My cherished post" in page
    reply = Post.query.filter(Post.body_html.contains("cherished")).one()
    assert reply.thread_id == thread.id
    assert queued_mailings(broker) == [(reply.id,)]


def test_build_reply_email_address(app) -> None:
    post = mock.Mock()
    post.id = 2
    post.thread_id = 3

    member = mock.Mock()
    member.id = 4

    result = build_reply_email_address("test", post, member, "example.com")
    expected = "test+P-en-3-4-c33d74de7b0cc35a086c539c0e8f4fc3@example.com"
    assert result == expected


def test_extract_mail_destination_1(app) -> None:
    test_address = "test+P-en-3-4-c33d74de7b0cc35a086c539c0e8f4fc3@example.com"
    infos = extract_email_destination(test_address)
    assert infos == ("en", "3", "4")


def test_extract_mail_destination_2(app) -> None:
    test_address = (
        "John Q Public <test+P-en-3-4-c33d74de7b0cc35a086c539c0e8f4fc3@example.com>"
    )
    infos = extract_email_destination(test_address)
    assert infos == ("en", "3", "4")


def test_extract_mail_destination_3(app) -> None:
    test_address = (
        '"John Q Public" <test+P-en-3-4-c33d74de7b0cc35a086c539c0e8f4fc3@example.com>'
    )
    infos = extract_email_destination(test_address)
    assert infos == ("en", "3", "4")


@pytest.fixture
def warnings() -> Iterator[list[str]]:
    """The warnings logged during the test."""
    messages: list[str] = []
    sink = logger.add(messages.append, level="WARNING", format="{message}")
    yield messages
    logger.remove(sink)


def test_a_reply_to_a_deleted_thread_is_dropped(
    app, db, community1, warnings: list[str]
) -> None:
    """The reply's thread no longer exists: dropped, not retried."""
    post = mock.Mock(id=1, thread_id=999999)
    message = email.message_from_string(get_string_from_file("notification.email"))
    with app.test_request_context():
        address = build_reply_email_address(
            "test", post, community1.test_user, "example.com"
        )
        message.replace_header("To", address)
        assert process_email(message) is False

    assert warnings == ["Reply to a thread that no longer exists: 999999\n"]
    assert Post.query.count() == 0


def _reply_by_email(app, thread: Thread, user) -> bool:
    message = email.message_from_string(get_string_from_file("notification.email"))
    post = mock.Mock(id=1, thread_id=thread.id)
    with app.test_request_context():
        address = build_reply_email_address("test", post, user, "example.com")
    message.replace_header("To", address)
    return process_email(message)


def test_a_reply_by_email_from_a_member_is_posted(app, db, community1) -> None:
    user = community1.test_user
    community1.set_membership(user, MEMBER)
    thread = started_thread(db, community1, user, "Budget 2027")

    with mock.patch("abilian.sbe.apps.forum.tasks.send_post_by_email"):
        assert _reply_by_email(app, thread, user) is True

    db.session.expire_all()
    assert len(thread.posts) == 2


def test_a_reply_by_email_from_someone_no_longer_a_member_is_dropped(
    app, db, community1, warnings: list[str]
) -> None:
    """The reply address is signed, and still works once its holder has left."""
    user = community1.test_user
    thread = started_thread(db, community1, user, "Budget 2027")
    community1.remove_membership(user)
    db.session.commit()

    assert _reply_by_email(app, thread, user) is False

    assert warnings == [f"Reply by a non-member to thread {thread.id}, dropped\n"]
    db.session.expire_all()
    assert len(thread.posts) == 1


def test_a_thread_without_a_title_comes_back_to_its_form(
    db: SQLAlchemy, client, community1
) -> None:
    """A refused form came back through `request.csrf_failed`, which is only set
    where CSRF is checked: in tests, the page failed instead."""
    user = community1.test_user
    community1.set_membership(user, MEMBER)
    db.session.commit()
    url = url_for("forum.new_thread", community_id=community1.slug)
    data = {"title": "", "message": "<p>Hello.</p>", "__action": "create"}

    with client_login(client, user):
        response = client.post(url, data=data)

    assert response.status_code == 200
    assert Thread.query.count() == 0
