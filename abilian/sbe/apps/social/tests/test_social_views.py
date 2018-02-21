from __future__ import absolute_import, print_function, unicode_literals

from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.testing import BaseTestCase


class TestSocialViews(BaseTestCase):

    no_login = True

    # Tests start here
    def test_home(self):
        response = self.client.get(url_for("social.home"))
        assert response.status_code == 200

    def test_users(self):
        response = self.client.get(url_for("social.users"))
        assert response.status_code == 200

    def test_groups(self):
        response = self.client.get(url_for("social.groups"))
        assert response.status_code == 200

    def test_user(self):
        user = User.query.all()[0]
        response = self.client.get(url_for("social.user", user_id=user.id))
        assert response.status_code == 200


# def test_home(client):
#     response = client.get(url_for("social.home"))
#     assert response.status_code == 200
#     # self.assert_valid(response)
#
#
# def test_users(client):
#     response = client.get(url_for("social.users"))
#     assert response.status_code == 200
#     # self.assert_valid(response)
#
#
# def test_groups(client):
#     response = client.get(url_for("social.groups"))
#     assert response.status_code == 200
#     # self.assert_valid(response)
#
#
# def test_user(client):
#     user = User.query.all()[0]
#     response = client.get(url_for("social.user", user_id=user.id))
#     assert response.status_code == 200
#     # self.assert_valid(response)
