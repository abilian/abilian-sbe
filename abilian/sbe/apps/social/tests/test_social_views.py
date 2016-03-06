from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.testing import BaseTestCase


class TestSocialViews(BaseTestCase):

    init_data = True
    no_login = True

    # Tests start here
    def test_home(self):
        response = self.client.get(url_for("social.home"))
        self.assert_200(response)
        self.assert_valid(response)

    def test_users(self):
        response = self.client.get(url_for("social.users"))
        self.assert_200(response)
        self.assert_valid(response)

    def test_groups(self):
        response = self.client.get(url_for("social.groups"))
        self.assert_200(response)
        self.assert_valid(response)

    def test_user(self):
        user = User.query.all()[0]
        response = self.client.get(url_for("social.user", user_id=user.id))
        self.assert_200(response)
        self.assert_valid(response)
