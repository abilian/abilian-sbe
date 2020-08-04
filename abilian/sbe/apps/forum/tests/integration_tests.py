from datetime import datetime, timedelta
from unittest import mock

from flask import url_for
from flask_login import login_user

from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.forum.tests.util import get_string_from_file
from abilian.testing.util import client_login

from ..cli import inject_email
from ..models import Post, Thread
from ..tasks import build_reply_email_address, extract_email_destination


def test_posts_ordering(db, community1):
    thread = Thread(community=community1, title="test ordering")
    db.session.add(thread)
    t1 = datetime(2014, 6, 20, 15, 0, 0)
    p1 = Post(thread=thread, body_html="post 1", created_at=t1)
    t2 = datetime(2014, 6, 20, 15, 1, 0)
    p2 = Post(thread=thread, body_html="post 2", created_at=t2)
    db.session.flush()
    p1_id, p2_id = p1.id, p2.id
    assert [p.id for p in thread.posts] == [p1_id, p2_id]

    # set post1 created after post2
    t1 = t1 + timedelta(minutes=2)
    p1.created_at = t1
    db.session.flush()
    db.session.expire(thread)  # force thread.posts refreshed from DB
    assert [p.id for p in thread.posts] == [p2_id, p1_id]


def test_thread_indexed(app, db, community1, community2, req_ctx):
    index_svc = app.services["indexing"]
    index_svc.start()
    security_svc = app.services["security"]
    security_svc.start()

    thread1 = Thread(title="Community 1", community=community1)
    db.session.add(thread1)

    thread2 = Thread(title="Community 2: other", community=community2)
    db.session.add(thread2)
    db.session.commit()

    index_svc = app.services["indexing"]
    obj_types = (Thread.entity_type,)

    login_user(community1.test_user)
    res = index_svc.search("community", object_types=obj_types)
    assert len(res) == 1
    hit = res[0]
    assert hit["object_key"] == thread1.object_key

    login_user(community2.test_user)
    res = index_svc.search("community", object_types=obj_types)
    assert len(res) == 1
    hit = res[0]
    assert hit["object_key"] == thread2.object_key


def test_forum_home(client, community1, login_admin, req_ctx):
    response = client.get(url_for("forum.index", community_id=community1.slug))
    assert response.status_code == 200


def test_create_thread_informative(app, db, client, community1, req_ctx):
    """Test with 'informative' community.

    No mail sent, unless user is MANAGER
    """
    user = community1.test_user
    assert community1.type == "informative"
    community1.set_membership(user, MEMBER)
    db.session.commit()

    title = "Brand new thread"
    content = "shiny thread message"
    url = url_for("forum.new_thread", community_id=community1.slug)
    data = {"title": title, "message": content}
    data["__action"] = "create"

    mail = app.extensions["mail"]
    with client_login(client, user):
        with mail.record_messages() as outbox:
            data["send_by_email"] = "y"  # actually should not be in html form
            response = client.post(url, data=data)
            assert response.status_code == 302
            # FIXME: this doesn't pass
            # assert len(outbox) == 0

        community1.set_membership(user, MANAGER)
        db.session.commit()

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


def test_build_reply_email_address(app, req_ctx):
    post = mock.Mock()
    post.id = 2
    post.thread_id = 3

    member = mock.Mock()
    member.id = 4

    result = build_reply_email_address("test", post, member, "example.com")
    expected = "test+P-en-3-4-a8f33983311589176c711111dc38d94d@example.com"
    assert result == expected


def test_extract_mail_destination(app, req_ctx):
    # app.config['MAIL_SENDER'] = 'test@testcase.app.tld'

    test_address = "test+P-en-3-4-a8f33983311589176c711111dc38d94d@example.com"
    infos = extract_email_destination(test_address)
    assert infos == ("en", "3", "4")

    test_address = (
        "John Q Public <test+P-en-3-4-a8f33983311589176c711111dc38d94d@example.com>"
    )
    infos = extract_email_destination(test_address)
    assert infos == ("en", "3", "4")

    test_address = (
        '"John Q Public" <test+P-en-3-4-a8f33983311589176c711111dc38d94d@example.com>'
    )
    infos = extract_email_destination(test_address)
    assert infos == ("en", "3", "4")


def test_create_thread_and_post(community1, client, app, db, req_ctx):
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
        data = {"title": title, "message": content}
        data["__action"] = "create"
        data["send_by_email"] = "y"
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


@mock.patch("fileinput.input")
@mock.patch("abilian.sbe.apps.forum.commands.process_email")
def test_parse_forum_email(mock_process_email, mock_email):
    """No processing is tested only parsing into a email.message and
    verifying inject_email() logic."""
    # first load a test email returned by the mock_email
    mock_email.return_value = get_string_from_file("notification.email")

    # test the parsing function
    inject_email()

    # assert the email is read
    assert mock_email.called
    # assert a call on the celery task was made implying a message creation
    assert mock_process_email.delay.called

    ##
    mock_email.reset_mock()
    mock_process_email.delay.reset_mock()
    assert not mock_email.called
    assert not mock_process_email.delay.called

    mock_email.return_value = get_string_from_file("defects.email")
    inject_email()
    assert mock_email.called
    assert not mock_process_email.delay.called
