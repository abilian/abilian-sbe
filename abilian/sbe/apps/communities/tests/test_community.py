# coding=utf-8
"""
"""
from __future__ import absolute_import, print_function, unicode_literals

from flask import url_for

from abilian.services.security import Admin

from .. import views
from ..models import Community
from .base import CommunityIndexingTestCase as BaseIndexingTestCase


class CommunityIndexingTestCase(BaseIndexingTestCase):

    def test_community_indexed(self):
        svc = self.svc
        obj_types = (Community.entity_type,)
        with self.login(self.user_no_community):
            res = svc.search('community', object_types=obj_types)
            assert len(res) == 0

        with self.login(self.user):
            res = svc.search('community', object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit['object_key'] == self.community.object_key

        with self.login(self.user_c2):
            res = svc.search('community', object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit['object_key'] == self.c2.object_key

    def test_default_view_kw_with_hit(self):
        with self.login(self.user):
            hit = self.svc.search(
                'community', object_types=(Community.entity_type,))[0]
            kw = views.default_view_kw({}, hit, hit['object_type'], hit['id'])

        assert kw == {'community_id': self.community.slug}


class CommunityWebTestCase(BaseIndexingTestCase):
    # FIXME later
    SQLALCHEMY_WARNINGS_AS_ERROR = False

    def test_index(self):
        with self.client_login(self.user.email, 'azerty'):
            response = self.client.get(url_for("communities.index"))
        self.assert_200(response)

    def test_community_home(self):
        url = self.app.default_view.url_for(self.community)
        user = self.user.email
        user_c2 = self.user_c2.email
        with self.client_login(user_c2, 'azerty'):
            response = self.client.get(url)
            assert response.status_code == 403

        with self.client_login(user, 'azerty'):
            response = self.client.get(url)
            assert response.status_code == 302
            expected_url = url_for(
                "wall.index", community_id=self.community.slug, _external=True)
            assert response.headers['Location'] == expected_url

    def test_community_settings(self):
        url = url_for('communities.settings', community_id=self.community.slug)
        with self.client_login(self.user.email, 'azerty'):
            response = self.client.get(url)
            assert response.status_code == 403

            self.app.services['security'].grant_role(self.user, Admin)
            response = self.client.get(url)
            self.assert_200(response)

            data = {
                '__action': 'edit',
                'name': 'edited community',
                'description': 'my community',
                'linked_group': '',
                'type': 'participative',
            }
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            assert response.headers['Location'] == \
                   'http://localhost/communities/{}/'.format(self.community.slug)

            community = Community.query.get(self.community.id)
            assert community.name == 'edited community'

    def test_new(self):
        with self.client_login(self.user.email, 'azerty'):
            response = self.client.get(url_for("communities.new"))
            assert response.status_code == 403

            self.app.services['security'].grant_role(self.user, Admin)
            response = self.client.get(url_for("communities.new"))
            assert response.status_code == 200

    def test_members(self):
        with self.client_login(self.user.email, 'azerty'):
            url = url_for(
                "communities.members", community_id=self.community.slug)
            response = self.client.get(url)
            self.assert_200(response)

            # test add user
            data = {'action': 'add-user-role', 'user': self.user_c2.id}
            response = self.client.post(url, data=data)
            assert response.status_code == 403

            self.app.services['security'].grant_role(self.user, Admin)
            data = {
                'action': 'add-user-role',
                'user': self.user_c2.id,
                'role': 'member',
            }
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            assert response.headers['Location'] == 'http://localhost' + url

            membership = [
                m for m in self.community.memberships if m.user == self.user_c2
            ][0]
            assert membership.role == 'member'

            data['action'] = 'set-user-role'
            data['role'] = 'manager'
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            assert response.headers['Location'] == 'http://localhost' + url

            self.session.expire(membership)
            assert membership.role == 'manager'

            # Community.query.session is not self.db.session, but web app session.
            community = Community.query.get(self.community.id)
            assert self.user_c2 in community.members

            # test delete
            data = {
                'action': 'delete',
                'user': self.user_c2.id,
                'membership':
                [m.id for m in community.memberships
                 if m.user == self.user_c2][0],
            }
            response = self.client.post(url, data=data)
            assert response.status_code == 302
            assert response.headers['Location'] == \
                   'http://localhost/communities/{}/members'.format(
                       self.community.slug)

            assert self.user_c2 not in community.members
