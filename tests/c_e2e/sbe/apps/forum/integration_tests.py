# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import email
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest
from flask import url_for
from flask_login import login_user

from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.forum.cli import do_inject_email
from abilian.sbe.apps.forum.models import Post, Thread
from abilian.sbe.apps.forum.tasks import (
    build_reply_email_address,
    extract_email_destination,
    process_email,
    send_post_by_email,
)
from abilian.sbe.apps.forum.views import ThreadCreate
from abilian.services import get_service, security_service
from tests.forum_util import get_string_from_file
from tests.util import client_login

if TYPE_CHECKING:
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


@pytest.mark.skip("Require fixing dramatiq tests to not loose session in test context")
def test_create_thread_informative_member(
    app, db: SQLAlchemy, client, community1, monkeypatch
) -> None:
    """Test with 'informative' community.

    No mail sent, unless user is MANAGER
    """

    def commit_success_no_task(self) -> None:
        if self.send_by_email:
            send_post_by_email(self.post.id)

    monkeypatch.setattr(ThreadCreate, "commit_success", commit_success_no_task)

    user = community1.test_user
    assert community1.type == "informative"
    community1.set_membership(user, MEMBER)
    db.session.commit()

    title = "Brand new thread"
    content = "shiny thread message"
    url = url_for("forum.new_thread", community_id=community1.slug)
    data = {"title": title, "message": content, "__action": "create"}

    mail = app.extensions["mail"]
    with client_login(client, user), mail.record_messages():
        data["send_by_email"] = "y"  # actually should not be in html form
        response = client.post(url, data=data)
        assert response.status_code == 302
        # FIXME: this doesn't pass
        # assert len(outbox) == 0


@pytest.mark.skip("Require fixing dramatiq tests to not loose session in test context")
def test_create_thread_informative_manager(
    app, db: SQLAlchemy, client, community1, monkeypatch
) -> None:
    """Test with 'informative' community.

    No mail sent, unless user is MANAGER
    """

    def commit_success_no_task(self) -> None:
        if self.send_by_email:
            send_post_by_email(self.post.id)

    monkeypatch.setattr(ThreadCreate, "commit_success", commit_success_no_task)

    user = community1.test_user
    assert community1.type == "informative"
    community1.set_membership(user, MANAGER)
    db.session.commit()

    title = "Brand new thread"
    content = "shiny thread message"
    url = url_for("forum.new_thread", community_id=community1.slug)
    data = {"title": title, "message": content, "__action": "create"}

    mail = app.extensions["mail"]
    with client_login(client, user):
        with mail.record_messages() as outbox:
            data["send_by_email"] = "y"  # should be in html form
            response = client.post(url, data=data)
            assert response.status_code == 302
            assert len(outbox) == 1

        with mail.record_messages() as outbox:
            del data["send_by_email"]
            response = client.post(url, data=data)
            assert response.status_code == 302
            assert len(outbox) == 0


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


@pytest.mark.skip("Require fixing dramatiq tests to not loose session in test context")
def test_create_thread_and_post(community1, client, app, db) -> None:
    community = community1
    user = community.test_user

    # activate email reply
    app.config["SBE_FORUM_REPLY_BY_MAIL"] = True

    # create a new user, add him/her to the current community as a MANAGER
    community.set_membership(user, MANAGER)
    db.session.commit()
    client_login(client, user)

    mail = app.extensions["mail"]
    with mail.record_messages() as outbox:
        title = "Brand new thread"
        content = "shiny thread message"
        url = url_for("forum.new_thread", community_id=community.slug)
        data = {
            "title": title,
            "message": content,
            "__action": "create",
            "send_by_email": "y",
        }
        response = client.post(url, data=data)
        assert response.status_code == 302

        # extract the thread_id from the redirection url in response
        threadid = response.location.rsplit("/", 2)[1]

        # retrieve the new thread, make sur it has the message
        url = url_for(
            "forum.thread", thread_id=threadid, community_id=community.slug, title=title
        )
        response = client.get(url)
        assert response.status_code == 200
        assert content in response.get_data(as_text=True)

        # check the email was sent with the new thread
        assert len(outbox) == 1
        assert outbox[0].subject == "[My Community] Brand new thread"

    # reset the outbox for checking threadpost email
    with mail.record_messages() as outbox:
        content = data["message"] = "my cherished post"
        del data["title"]
        response = client.post(url, data=data)
        assert response.status_code == 302

        # retrieve the new thread, make sur it has the message
        url = url_for(
            "forum.thread", thread_id=threadid, community_id=community.slug, title=title
        )
        response = client.get(url)
        assert response.status_code == 200
        assert content in response.get_data(as_text=True)

        # check the email was sent with the new threadpost
        assert len(outbox) == 1
        expected = "[My Community] Brand new thread"
        assert str(outbox[0].subject) == expected


@pytest.mark.skip("Require fixing dramatiq tests to not loose session in test context")
@mock.patch("fileinput.input")
@mock.patch("abilian.sbe.apps.forum.cli.process_email")
def test_parse_forum_email(mock_process_email, mock_email) -> None:
    """No processing is tested only parsing into a email.message and
    verifying inject_email() logic."""
    # first load a test email returned by the mock_email
    mock_email.return_value = get_string_from_file("notification.email")

    # test the parsing function
    do_inject_email()

    # assert the email is read
    assert mock_email.called
    # assert a call on the task was made implying a message creation
    assert mock_process_email.delay.called

    ##
    mock_email.reset_mock()
    mock_process_email.delay.reset_mock()
    assert not mock_email.called
    assert not mock_process_email.delay.called

    mock_email.return_value = get_string_from_file("defects.email")
    do_inject_email()
    assert mock_email.called
    assert not mock_process_email.delay.called


def test_a_reply_to_a_deleted_thread_is_dropped(app, db, community1) -> None:
    """The reply's thread no longer exists: dropped, not retried."""
    post = mock.Mock(id=1, thread_id=999999)
    message = email.message_from_string(get_string_from_file("notification.email"))
    with app.test_request_context():
        address = build_reply_email_address(
            "test", post, community1.test_user, "example.com"
        )
        message.replace_header("To", address)
        assert process_email(message) is False
