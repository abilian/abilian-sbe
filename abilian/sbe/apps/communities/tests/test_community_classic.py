# coding=utf-8
"""
TODO: remove once the pytest-based tests all pass.
"""
from __future__ import absolute_import, print_function, unicode_literals

from abilian.services.security import Admin
from abilian.testing.util import path_from_url
from flask import url_for

from ..models import Community
from .base import CommunityIndexingTestCase as BaseIndexingTestCase


class CommunityWebTestCase(BaseIndexingTestCase):
    # FIXME later
    SQLALCHEMY_WARNINGS_AS_ERROR = False

    def test_index(self):
        with self.client_login(self.user.email, "azerty"):
            response = self.client.get(url_for("communities.index"))
            assert response.status_code == 200

    def test_community_home(self):
        url = self.app.default_view.url_for(self.community)
        user = self.user.email
        user_c2 = self.user_c2.email
        with self.client_login(user_c2, "azerty"):
            response = self.client.get(url)
            assert response.status_code == 403

        with self.client_login(user, "azerty"):
            response = self.client.get(url)
            assert response.status_code == 302
            expected_url = url_for(
                "wall.index", community_id=self.community.slug, _external=True
            )
            assert response.location == expected_url

    def test_community_settings(self):
        url = url_for("communities.settings", community_id=self.community.slug)
        with self.client_login(self.user.email, "azerty"):
            response = self.client.get(url)
            assert response.status_code == 403

            self.app.services["security"].grant_role(self.user, Admin)
            response = self.client.get(url)
            assert response.status_code == 200

            data = {
                "__action": "edit",
                "name": "edited community",
                "description": "my community",
                "linked_group": "",
                "type": "participative",
            }
            response = self.client.post(url, data=data)
            assert response.status_code == 302

            path = path_from_url(response.location)
            assert path == "/communities/" + self.community.slug + "/"

            community = Community.query.get(self.community.id)
            assert community.name == "edited community"

    def test_new(self):
        with self.client_login(self.user.email, "azerty"):
            response = self.client.get(url_for("communities.new"))
            assert response.status_code == 403

            self.app.services["security"].grant_role(self.user, Admin)
            response = self.client.get(url_for("communities.new"))
            assert response.status_code == 200

    def test_members(self):
        with self.client_login(self.user.email, "azerty"):
            url = url_for("communities.members", community_id=self.community.slug)
            response = self.client.get(url)
            assert response.status_code == 200

            # test add user
            data = {"action": "add-user-role", "user": self.user_c2.id}
            response = self.client.post(url, data=data)
            assert response.status_code == 403

            self.app.services["security"].grant_role(self.user, Admin)
            data = {
                "action": "add-user-role",
                "user": self.user_c2.id,
                "role": "member",
            }
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            path = path_from_url(response.location)
            assert path == url

            membership = [
                m for m in self.community.memberships if m.user == self.user_c2
            ][0]
            assert membership.role == "member"

            data["action"] = "set-user-role"
            data["role"] = "manager"
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            path = path_from_url(response.location)
            assert path == url

            self.session.expire(membership)
            assert membership.role == "manager"

            # Community.query.session is not self.db.session, but web app
            # session.
            community = Community.query.get(self.community.id)
            assert self.user_c2 in community.members

            # test delete
            data = {
                "action": "delete",
                "user": self.user_c2.id,
                "membership": [
                    m.id for m in community.memberships if m.user == self.user_c2
                ][0],
            }
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            path = path_from_url(response.location)
            assert path == "/communities/" + self.community.slug + "/members"

            assert self.user_c2 not in community.members
