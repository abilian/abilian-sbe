# coding=utf-8
"""
"""
from __future__ import absolute_import

from datetime import datetime, timedelta
from email.parser import FeedParser
from unittest import TestCase

import pytest
from flask import url_for
from mock import Mock, patch
from pathlib import Path

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.communities.tests.base import (CommunityBaseTestCase,
                                                     CommunityIndexingTestCase)
from abilian.sbe.testing import BaseTestCase

from ..commands import inject_email
from ..models import Post, Thread, ThreadClosedError
from ..tasks import (build_reply_email_address, extract_email_destination,
                     process)


class Test(TestCase):

    def test_create_post(self):
        thread = Thread(title="Test thread")
        post = thread.create_post()
        assert post in thread.posts
        assert post.name == u'Test thread'

        thread.title = u'new title'
        assert thread.name == u'new title'
        assert post.name == u'new title'

    def test_closed_property(self):
        thread = Thread(title=u'Test Thread')
        assert thread.closed is False
        thread.closed = True
        assert thread.closed is True
        thread.closed = 0
        assert thread.closed is False
        thread.closed = 1
        assert thread.closed is True
        assert thread.meta['abilian.sbe.forum']['closed'] is True

    def test_thread_closed_guard(self):
        thread = Thread(title=u'Test Thread')
        thread.create_post()
        thread.closed = True

        with pytest.raises(ThreadClosedError):
            thread.create_post()

        p = Post(body_html=u'ok')

        with pytest.raises(ThreadClosedError):
            p.thread = thread

        thread.closed = False
        p.thread = thread
        assert len(thread.posts) == 2

        thread.closed = True
        with pytest.raises(ThreadClosedError):
            del thread.posts[0]

        assert len(thread.posts) == 2

        with pytest.raises(ThreadClosedError):
            # actually thread.posts will be replaced by `[]` and we can't prevent
            # this, but exception has been raised
            thread.posts = []

        thread.closed = False
        thread.posts = [p]
        thread.closed = True
        assert thread.posts == [p]
        assert p.thread is thread
        with pytest.raises(ThreadClosedError):
            p.thread = None

    def test_change_thread_copy_name(self):
        thread = Thread(title=u'thread 1')
        thread2 = Thread(title=u'thread 2')
        post = Post(thread=thread, body_html=u'post content')
        assert post.name == thread.name

        post.thread = thread2
        assert post.name == thread2.name

    def test_task_process_email(self):
        """
      test the process_email function
    """
        marker = u'_____Write above this line to post_____'

        message = get_emailmessage_from_file('reply.email')
        newpost = process(message, marker)
        assert newpost

        message = get_emailmessage_from_file('reply_nocharset_specified.email')
        newpost = process(message, marker)
        assert newpost

        message = get_emailmessage_from_file('reply_no_marker.email')
        self.assertRaises(LookupError, process, message, marker)

        # dubious check
        message = get_emailmessage_from_file('reply_no_textpart.email')
        self.assertRaises(LookupError, process, message, marker)


class IndexingTestCase(CommunityIndexingTestCase):

    def test_thread_indexed(self):
        thread = Thread(title=u'Community 1', community=self.community)
        self.session.add(thread)
        thread_other = Thread(title=u'Community 2: other', community=self.c2)
        self.session.add(thread_other)
        self.session.commit()

        svc = self.svc
        obj_types = (Thread.entity_type,)
        with self.login(self.user_no_community):
            res = svc.search(u'community', object_types=obj_types)
            assert len(res) == 0

        with self.login(self.user):
            res = svc.search(u'community', object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit['object_key'] == thread.object_key

        with self.login(self.user_c2):
            res = svc.search(u'community', object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit['object_key'] == thread_other.object_key


class NoLoginViewTest(CommunityBaseTestCase):
    """
    Test correct url response, without login or security involved
    """

    def test(self):
        response = self.client.get(url_for("forum.index",
                                           community_id=self.community.slug))
        self.assert200(response)


class ViewTestCase(CommunityBaseTestCase):
    no_login = False
    SERVICES = ('security',)

    def test_posts_ordering(self):
        thread = Thread(community=self.community, title=u'test ordering')
        self.session.add(thread)
        t1 = datetime(2014, 6, 20, 15, 0, 0)
        p1 = Post(thread=thread, body_html=u'post 1', created_at=t1)
        t2 = datetime(2014, 6, 20, 15, 1, 0)
        p2 = Post(thread=thread, body_html=u'post 2', created_at=t2)
        self.session.flush()
        p1_id, p2_id = p1.id, p2.id
        assert [p.id for p in thread.posts] == [p1_id, p2_id]

        # set post1 created after post2
        t1 = t1 + timedelta(minutes=2)
        p1.created_at = t1
        self.session.flush()
        self.session.expire(thread)  # force thread.posts refreshed from DB
        assert [p.id for p in thread.posts] == [p2_id, p1_id]

    def test_create_thread_and_post(self):
        # activate email reply
        self.app.config['SBE_FORUM_REPLY_BY_MAIL'] = True
        self.app.config['MAIL_ADDRESS_TAG_CHAR'] = u'+'

        # create a new user, add him/her to the current community as a MANAGER
        self.user = User(email=u'user_1@example.com',
                         password='azerty',
                         can_login=True)
        self.session.add(self.user)
        self.community.set_membership(self.user, MANAGER)
        self.session.commit()
        self.client_login(self.user.email, self.user.password)

        mail = self.app.extensions['mail']
        with mail.record_messages() as outbox:
            title = u"Brand new thread"
            content = u"shiny thread message"
            url = url_for("forum.new_thread", community_id=self.community.slug)
            data = dict(title=title, message=content)
            data['__action'] = u"create"
            data['send_by_email'] = u"y"
            response = self.client.post(url, data=data)
            self.assertStatus(response, 302)

            # extract the thread_id from the redirection url in response
            threadid = response.location.rsplit('/', 2)[1]

            # retrieve the new thread, make sur it has the message
            url = url_for("forum.thread",
                          thread_id=threadid,
                          community_id=self.community.slug,
                          title=title)
            response = self.client.get(url)
            self.assertStatus(response, 200)
            self.assertIn(content, response.data.decode("utf-8"))

            # check the email was sent with the new thread
            assert len(outbox) == 1
            assert outbox[0].subject == u'[My Community] Brand new thread'

        # reset the outbox for checking threadpost email
        with mail.record_messages() as outbox:
            content = data['message'] = u"my cherished post"
            del data['title']
            response = self.client.post(url, data=data)
            self.assertStatus(response, 302)

            # retrieve the new thread, make sur it has the message
            url = url_for("forum.thread",
                          thread_id=threadid,
                          community_id=self.community.slug,
                          title=title)
            response = self.client.get(url)
            self.assertStatus(response, 200)
            self.assertIn(content, response.data.decode("utf-8"))

            # check the email was sent with the new threadpost
            assert len(outbox) == 1
            assert unicode(outbox[
                0].subject) == u'[My Community] Brand new thread'

    def test_create_thread_informative(self):
        """
    Test with 'informative' community. No mail sent, unless user is MANAGER
    """
        assert self.community.type == 'informative'
        # create a new user, add him/her to the current community
        self.user = User(email=u'user_1@example.com',
                         password='azerty',
                         can_login=True)
        self.session.add(self.user)
        self.community.set_membership(self.user, MEMBER)
        self.session.commit()

        title = u"Brand new thread"
        content = u"shiny thread message"
        url = url_for("forum.new_thread", community_id=self.community.slug)
        data = dict(title=title, message=content)
        data['__action'] = u"create"

        mail = self.app.extensions['mail']
        self.client_login(self.user.email, self.user.password)

        with mail.record_messages() as outbox:
            data['send_by_email'] = u"y"  # actually should not be in html form
            response = self.client.post(url, data=data)
            self.assertStatus(response, 302)
            assert len(outbox) == 0

        self.community.set_membership(self.user, MANAGER)
        self.session.commit()

        with mail.record_messages() as outbox:
            data['send_by_email'] = u"y"  # should be in html form
            response = self.client.post(url, data=data)
            self.assertStatus(response, 302)
            assert len(outbox) == 1

        with mail.record_messages() as outbox:
            del data['send_by_email']
            response = self.client.post(url, data=data)
            self.assertStatus(response, 302)
            assert len(outbox) == 0

        self.client_logout()


def get_string_from_file(filename='notification.email'):
    """Load a test email return as string."""
    filepath = Path(__file__).parent / 'data' / filename
    with filepath.open('rt', encoding='utf-8') as email_file:
        email_string = email_file.read()
    return email_string


def get_emailmessage_from_file(filename='notification.email'):
    """Load a mail parse it into a email.message."""
    email_string = get_string_from_file(filename)
    parser = FeedParser()
    parser.feed(email_string)
    email_message = parser.close()
    return email_message


class CommandsTest(TestCase):

    @patch('fileinput.input')
    @patch('abilian.sbe.apps.forum.commands.process_email')
    def test_parse_forum_email(self, mock_process_email, mock_email):
        """
        No processing is tested only parsing into a email.message
        and verifying inject_email() logic
        """
        # first load a test email returned by the mock_email
        mock_email.return_value = get_string_from_file('notification.email')

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

        mock_email.return_value = get_string_from_file('defects.email')
        inject_email()
        assert mock_email.called
        assert not mock_process_email.delay.called


class TasksTest(BaseTestCase):

    def test_build_reply_email_address(self):
        expected_reply_address = 'test+P-fr-3-4-LJXUDQHH3ELLN4KZSLLSA7SHWI@testcase.app.tld'
        self.app.config['MAIL_ADDRESS_TAG_CHAR'] = u'+'
        post = Mock()
        post.id = 2
        post.thread_id = 3
        member = Mock()
        member.id = 4
        with self.app.test_request_context(
                '/build_reply_email_address',
                headers=[('Accept-Language', u'fr')]):
            replyto = build_reply_email_address('test', post, member,
                                                'testcase.app.tld')
        self.assertIn(expected_reply_address, replyto)

    def test_extract_mail_destination(self):
        self.app.config['MAIL_ADDRESS_TAG_CHAR'] = u'+'
        self.app.config['MAIL_SENDER'] = u'test@testcase.app.tld'
        test_address = 'test+test+P-fr-3-4-LJXUDQHH3ELLN4KZSLLSA7SHWI@testcase.app.tld'
        infos = extract_email_destination(test_address)
        self.assertIn(u'fr', infos[0])  # locale
        self.assertIn(u'3', infos[1])  # thread_id
        self.assertIn(u'4', infos[2])  # post.id
