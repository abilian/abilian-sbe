# Copyright (c) 2012-2026, Abilian SAS

"""Mon fil, the news of the user's communities, and a community's home, its own."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for

from abilian.sbe.apps.communities.models import MANAGER, Community
from abilian.sbe.apps.forum.models import Thread
from abilian.services.activity.models import ActivityEntry
from abilian.services.security import ADMIN, security
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy


def _started(db: SQLAlchemy, community: Community, author: User, title: str) -> None:
    """`author` starts a thread in `community`, as the forum records it."""
    thread = Thread(title=title, community=community)
    thread.creator = thread.owner = author
    post = thread.create_post(body_html="<p>The <b>first</b> words of it.</p>")
    post.creator = post.owner = author
    db.session.add(thread)
    db.session.flush()
    # As the activity service writes it, types included.
    db.session.add(
        ActivityEntry(
            actor=author,
            verb="post",
            object=thread,
            object_type=thread.entity_type,
            target=community,
            target_type=community.entity_type,
        )
    )
    db.session.commit()


def test_my_feed_shows_the_news_of_my_communities(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = community1.test_user
    _started(db, community1, member, "A thread in my community")

    with client_login(client, member):
        response = client.get(url_for("main.home"))

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "A thread in my community" in html
    assert "started a discussion" in html
    # The post's text, without its markup.
    assert "The first words of it." in html
    # The community, in the entry and in the column beside the feed.
    assert html.count(community1.name) >= 2
    # On the Abilian Design System, not on Tailwind.
    assert "ads/ads.css" in html
    assert "/vite/" not in html


def test_my_feed_leaves_out_the_communities_i_am_not_in(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    elsewhere = Community(name="Somewhere else")
    db.session.add(elsewhere)
    db.session.flush()
    _started(db, elsewhere, community1.test_user, "A thread elsewhere")

    with client_login(client, community1.test_user):
        html = client.get(url_for("main.home")).get_data(as_text=True)

    assert "A thread elsewhere" not in html


def test_an_anonymous_visitor_is_asked_to_log_in(
    app: Application, client: FlaskClient
) -> None:
    response = client.get(url_for("main.home"))

    assert response.status_code == 302
    assert url_for("login.login_form") in response.location


def test_the_old_feed_leads_to_my_feed(
    app: Application, client: FlaskClient, login_admin: User
) -> None:
    response = client.get(url_for("social.home"))

    assert response.status_code == 302
    assert response.location.endswith(url_for("main.home"))


def test_the_bar_offers_administration_to_an_admin_only(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    # `has_role` answers True for everyone while the service is stopped.
    ensure_services_started(["security"])
    member = community1.test_user
    admin_link = f'href="{url_for("admin.dashboard")}'

    with client_login(client, member):
        assert admin_link not in client.get(url_for("main.home")).get_data(as_text=True)

    security.grant_role(member, ADMIN)
    db.session.commit()
    with client_login(client, member):
        assert admin_link in client.get(url_for("main.home")).get_data(as_text=True)


def test_a_community_home_shows_its_news_and_its_tools(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    member = community1.test_user
    _started(db, community1, member, "A thread in this community")

    with client_login(client, member):
        response = client.get(url_for("wall.index", community_id=community1.slug))

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "A thread in this community" in html
    # The tabs, the forum first; the settings are not a tab.
    assert html.index(">Home<") < html.index(">Discussions<")
    assert ">Settings<" not in html
    # A member doesn't run the community.
    assert url_for("communities.settings", community_id=community1.slug) not in html


def test_a_manager_finds_the_settings_in_the_header(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    manager = community1.test_user
    community1.set_membership(manager, MANAGER)
    db.session.commit()

    with client_login(client, manager):
        html = client.get(url_for("wall.index", community_id=community1.slug)).get_data(
            as_text=True
        )

    assert url_for("communities.settings", community_id=community1.slug) in html
    assert "Invite members" in html
