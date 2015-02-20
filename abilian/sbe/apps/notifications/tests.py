# coding=utf-8
"""
"""
from __future__ import absolute_import

from abilian.core.models.subjects import User
from abilian.web import url_for

from abilian.sbe.testing import BaseTestCase
from abilian.sbe.apps.notifications.tasks.social import \
     generate_unsubscribe_token


class TestNotificationViews(BaseTestCase):

  def get_setup_config(self):
    cfg = super(TestNotificationViews, self).get_setup_config()
    # "unsubscribe" url must be accessible without csrf, so user can post even
    # if he's not authentified
    cfg.CSRF_ENABLED = True
    cfg.WTF_CSRF_ENABLED = True
    return cfg

  def setUp(self):
    super(TestNotificationViews, self).setUp()
    self.user = User(email=u'user_1@example.com', password='azerty',
                     can_login=True)
    self.session.add(self.user)
    self.session.commit()

  def test_unsubscribe(self):
    preferences = self.app.services['preferences']
    preferences.set_preferences(self.user, **{'sbe:notifications:daily': True})
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
