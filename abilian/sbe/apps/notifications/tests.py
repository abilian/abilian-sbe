# coding=utf-8
"""
"""
from __future__ import absolute_import

from flask import render_template

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import WRITER
from abilian.sbe.apps.communities.tests.base import CommunityBaseTestCase
from abilian.sbe.apps.notifications.tasks.social import (
    CommunityDigest, generate_unsubscribe_token)
from abilian.sbe.testing import BaseTestCase
from abilian.web import url_for


class TestNotificationViews(BaseTestCase):

    def get_setup_config(self):
        cfg = super(TestNotificationViews, self).get_setup_config()
        # "unsubscribe" url must be accessible without csrf, so user can post even
        # if he's not authentified
        cfg.CSRF_ENABLED = True
        cfg.WTF_CSRF_ENABLED = True
        cfg.NO_LOGIN = False
        return cfg

    def setUp(self):
        super(TestNotificationViews, self).setUp()
        self.user = User(email=u'user_1@example.com',
                         password='azerty',
                         can_login=True)
        self.session.add(self.user)
        self.session.commit()

    def test_unsubscribe(self):
        preferences = self.app.services['preferences']
        preferences.set_preferences(self.user, **{'sbe:notifications:daily':
                                                  True})
        token = generate_unsubscribe_token(self.user)
        url = url_for('notifications.unsubscribe_sbe', token=token)

        r = self.client.get(url)
        self.assert_200(r)
        prefs = preferences.get_preferences(self.user)
        self.assertTrue(prefs['sbe:notifications:daily'])

        r = self.client.post(url)
        self.assert_200(r)
        prefs = preferences.get_preferences(self.user)
        self.assertFalse(prefs['sbe:notifications:daily'])


class NotificationTestCase(CommunityBaseTestCase):

    def setUp(self):
        super(NotificationTestCase, self).setUp()
        self.user = User(email=u'user_1@example.com',
                         password='azerty',
                         can_login=True)
        self.session.add(self.user)
        self.community.set_membership(self.user, WRITER)
        self.session.commit()

    def test_mail_templates(self):
        # this actually tests that templates are parsed without errors, not the
        # rendered content
        digests = [CommunityDigest(self.community)]
        token = generate_unsubscribe_token(self.user)
        render_template("notifications/daily-social-digest.txt",
                        digests=digests,
                        token=token)
        render_template("notifications/daily-social-digest.html",
                        digests=digests,
                        token=token)
