# coding=utf-8
""""""
from __future__ import absolute_import, print_function, unicode_literals

from abilian.services.security import Admin
from abilian.testing.util import client_login
from flask import url_for
from flask_login import current_user
from pytest import mark

from ..models import Community


def test_index(app, client, community1):
    security_service = app.services["security"]
    security_service.start()

    user = community1.test_user
    with client_login(client, user):
        response = client.get(url_for("communities.index"))
        assert response.status_code == 200


def test_community_home(app, client, community1, community2):
    security_service = app.services["security"]
    security_service.start()

    url = app.default_view.url_for(community1)

    user1 = community1.test_user
    with client_login(client, user1):
        response = client.get(url)
        assert response.status_code == 302
        expected_url = url_for(
            "wall.index", community_id=community1.slug, _external=True
        )
        assert response.location == expected_url

    user2 = community2.test_user
    with client_login(client, user2):
        response = client.get(url)
        assert response.status_code == 403


def test_new(app, client, community1):
    security_service = app.services["security"]
    security_service.start()

    user = community1.test_user

    with client_login(client, user):
        response = client.get(url_for("communities.new"))
        assert response.status_code == 403

        app.services["security"].grant_role(user, Admin)
        response = client.get(url_for("communities.new"))
        assert response.status_code == 200


@mark.skip  # TODO: fix
def test_community_settings(app, client, community1):
    security_service = app.services["security"]
    security_service.start()

    url = url_for("communities.settings", community_id=community1.slug)
    user = community1.test_user

    with client_login(client, user):
        response = client.get(url)
        assert response.status_code == 403

        app.services["security"].grant_role(user, Admin)
        response = client.get(url)
        assert response.status_code == 200

        data = {
            "__action": "edit",
            "name": "edited community",
            "description": "my community",
            "linked_group": "",
            "type": "participative",
        }
        response = client.post(url, data=data)
        assert response.status_code == 302
        expected_url = "http://localhost/communities/{}/".format(community1.slug)
        assert response.location == expected_url

        community = Community.query.get(community1.id)
        assert community.name == "edited community"


@mark.skip  # TODO: fix
def test_members(app, client, db, community1, community2):
    security_service = app.services["security"]
    security_service.start()

    user1 = community1.test_user
    user2 = community2.test_user

    with client_login(client, user1):
        url = url_for("communities.members", community_id=community1.slug)
        response = client.get(url)
        assert response.status_code == 200

        # test add user
        data = {"action": "add-user-role", "user": user2.id}
        response = client.post(url, data=data)
        assert response.status_code in (403, 400)

        app.services["security"].grant_role(user1, Admin)

        data = {"action": "add-user-role", "user": user2.id, "role": "member"}
        response = client.post(url, data=data)
        assert response.status_code == 302
        assert response.location == "http://localhost" + url

        membership = [m for m in community1.memberships if m.user == user2][0]
        assert membership.role == "member"

        data["action"] = "set-user-role"
        data["role"] = "manager"
        response = client.post(url, data=data)
        assert response.status_code == 302
        assert response.location == "http://localhost" + url

        db.session.expire(membership)
        assert membership.role == "manager"

        # Community.query.session is not self.db.session, but web app
        # session.
        community = Community.query.get(community1.id)
        assert user2 in community.members

        # test delete
        data = {
            "action": "delete",
            "user": user2.id,
            "membership": [m.id for m in community1.memberships if m.user == user2][0],
        }
        response = client.post(url, data=data)
        expected_url = "http://localhost/communities/{}/members".format(community1.slug)
        assert response.status_code == 302
        assert response.location == expected_url

        assert user2 not in community.members
