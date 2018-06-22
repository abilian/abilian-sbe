# coding=utf-8
"""
TODO: remove when refactoring done.
"""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from abilian.core.models.subjects import User
from flask import url_for
from mock import patch
from six import text_type

from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.communities.tests.base import CommunityBaseTestCase
from abilian.sbe.apps.forum.tests.util import get_string_from_file

from ..commands import inject_email


class NoLoginViewTest(CommunityBaseTestCase):
    """Test correct url response, without login or security involved."""

    def test(self):
        response = self.client.get(
            url_for("forum.index", community_id=self.community.slug)
        )
        assert response.status_code == 200


class ViewTestCase(CommunityBaseTestCase):
    no_login = False
    SERVICES = ("security",)

    def test_create_thread_and_post(self):
        # activate email reply
        self.app.config["SBE_FORUM_REPLY_BY_MAIL"] = True
        self.app.config["MAIL_ADDRESS_TAG_CHAR"] = "+"

        # create a new user, add him/her to the current community as a MANAGER
        self.user = User(email="user_1@example.com", password="azerty", can_login=True)
        self.session.add(self.user)
        self.community.set_membership(self.user, MANAGER)
        self.session.commit()
        self.client_login(self.user.email, self.user.password)

        mail = self.app.extensions["mail"]
        with mail.record_messages() as outbox:
            title = "Brand new thread"
            content = "shiny thread message"
            url = url_for("forum.new_thread", community_id=self.community.slug)
            data = {"title": title, "message": content}
            data["__action"] = "create"
            data["send_by_email"] = "y"
            response = self.client.post(url, data=data)
            assert response.status_code == 302

            # extract the thread_id from the redirection url in response
            threadid = response.location.rsplit("/", 2)[1]

            # retrieve the new thread, make sur it has the message
            url = url_for(
                "forum.thread",
                thread_id=threadid,
                community_id=self.community.slug,
                title=title,
            )
            response = self.client.get(url)
            assert response.status_code == 200
            assert content in response.data.decode("utf-8")

            # check the email was sent with the new thread
            assert len(outbox) == 1
            assert outbox[0].subject == "[My Community] Brand new thread"

        # reset the outbox for checking threadpost email
        with mail.record_messages() as outbox:
            content = data["message"] = "my cherished post"
            del data["title"]
            response = self.client.post(url, data=data)
            assert response.status_code == 302

            # retrieve the new thread, make sur it has the message
            url = url_for(
                "forum.thread",
                thread_id=threadid,
                community_id=self.community.slug,
                title=title,
            )
            response = self.client.get(url)
            assert response.status_code == 200
            assert content in response.data.decode("utf-8")

            # check the email was sent with the new threadpost
            assert len(outbox) == 1
            expected = "[My Community] Brand new thread"
            assert text_type(outbox[0].subject) == expected

    def test_create_thread_informative(self):
        """Test with 'informative' community.

        No mail sent, unless user is MANAGER
        """
        assert self.community.type == "informative"
        # create a new user, add him/her to the current community
        self.user = User(email="user_1@example.com", password="azerty", can_login=True)
        self.session.add(self.user)
        self.community.set_membership(self.user, MEMBER)
        self.session.commit()

        title = "Brand new thread"
        content = "shiny thread message"
        url = url_for("forum.new_thread", community_id=self.community.slug)
        data = {"title": title, "message": content}
        data["__action"] = "create"

        mail = self.app.extensions["mail"]
        self.client_login(self.user.email, self.user.password)

        with mail.record_messages() as outbox:
            data["send_by_email"] = "y"  # actually should not be in html form
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            assert len(outbox) == 0

        self.community.set_membership(self.user, MANAGER)
        self.session.commit()

        with mail.record_messages() as outbox:
            data["send_by_email"] = "y"  # should be in html form
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            assert len(outbox) == 1

        with mail.record_messages() as outbox:
            del data["send_by_email"]
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            assert len(outbox) == 0

        self.client_logout()


class CommandsTest(TestCase):
    @patch("fileinput.input")
    @patch("abilian.sbe.apps.forum.commands.process_email")
    def test_parse_forum_email(self, mock_process_email, mock_email):
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
