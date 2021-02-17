from flask import render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug import Client

from abilian.core.models.subjects import User
from abilian.sbe.app import Application
from abilian.sbe.apps.communities.models import WRITER, Community
from abilian.sbe.apps.notifications.tasks.social import (
    CommunityDigest,
    generate_unsubscribe_token,
)
from abilian.services.preferences.service import PreferenceService
from abilian.web import url_for


def test_unsubscribe(app: Application, client: Client, db: SQLAlchemy, app_context):
    user = User(email="user_1@example.com", password="abc", can_login=True)
    db.session.add(user)
    db.session.commit()

    preferences: PreferenceService = app.services["preferences"]
    preferences.set_preferences(user, **{"sbe:notifications:daily": True})
    token = generate_unsubscribe_token(user)
    url = url_for("notifications.unsubscribe_sbe", token=token)

    # Not need to login, since we're using the unsubscribe token

    response = client.get(url)
    assert response.status_code == 200
    prefs = preferences.get_preferences(user)
    assert prefs["sbe:notifications:daily"]

    response = client.post(url)
    assert response.status_code == 200
    prefs = preferences.get_preferences(user)
    assert not prefs["sbe:notifications:daily"]


def test_mail_templates(db: SQLAlchemy, app_context):
    # this actually tests that templates are parsed without errors, not the
    # rendered content
    user = User(email="user_1@example.com")
    db.session.add(user)
    community = Community(name="My Community")
    db.session.add(community)
    community.set_membership(user, WRITER)
    db.session.commit()

    digests = [CommunityDigest(community)]
    token = generate_unsubscribe_token(user)
    ctx = {"digests": digests, "token": token}
    render_template("notifications/daily-social-digest.html", **ctx)
