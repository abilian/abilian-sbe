# Copyright (c) 2012-2026, Abilian SAS

"""Mon fil, the news of the user's communities, and a community's home, its own."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import unescape
from typing import TYPE_CHECKING

from flask import url_for

from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.models import MANAGER, Community
from abilian.sbe.apps.forum.models import Thread
from abilian.services import get_service
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


def test_my_feed_keeps_one_kind_of_news_when_asked(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = community1.test_user
    _started(db, community1, member, "A thread in my community")

    with client_login(client, member):
        discussions = client.get(url_for("main.home", kind="discussions"))
        documents = client.get(url_for("main.home", kind="documents"))
        unknown = client.get(url_for("main.home", kind="nonsense"))

    assert "A thread in my community" in discussions.get_data(as_text=True)
    html = documents.get_data(as_text=True)
    assert "A thread in my community" not in html
    assert 'href="/?kind=documents" aria-current="page"' in html
    assert unknown.status_code == 404


def test_my_feed_lists_the_events_to_come_in_my_communities(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    elsewhere = Community(name="Somewhere else")
    soon = datetime.now() + timedelta(days=3)
    long_ago = datetime(2020, 1, 6, 9)
    for title, community, start in (
        ("Soon in mine", community1, soon),
        ("Soon elsewhere", elsewhere, soon),
        ("Long ago in mine", community1, long_ago),
    ):
        db.session.add(
            Event(
                title=title,
                community=community,
                start=start,
                end=start + timedelta(hours=2),
            )
        )
    db.session.commit()

    with client_login(client, community1.test_user):
        html = client.get(url_for("main.home")).get_data(as_text=True)

    coming = html.split('id="coming"')[1]
    assert "Soon in mine" in coming
    assert "Soon elsewhere" not in coming
    assert "Long ago in mine" not in coming


def _read_until(user: User, moment: datetime) -> None:
    get_service("preferences").set_preferences(
        user, **{"feed:read_until": moment.isoformat()}
    )


def _news_then_older_news(db: SQLAlchemy, community: Community) -> User:
    """A thread from two days ago, read already, and one from now, not yet."""
    member = community.test_user
    _started(db, community, member, "An older thread")
    older = ActivityEntry.query.one()
    older.happened_at = datetime.utcnow() - timedelta(days=2)
    _read_until(member, datetime.utcnow() - timedelta(days=1))
    _started(db, community, member, "A newer thread")
    return member


def test_on_a_first_visit_nothing_is_new(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = community1.test_user
    _started(db, community1, member, "A thread in my community")

    with client_login(client, member):
        html = client.get(url_for("main.home")).get_data(as_text=True)

    assert "Mark all as read" not in html
    assert ">New</span>" not in html
    preferences = get_service("preferences").get_preferences(member)
    assert "feed:read_until" in preferences


def test_what_came_since_i_marked_my_feed_read_is_new(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = _news_then_older_news(db, community1)

    with client_login(client, member):
        html = client.get(url_for("main.home")).get_data(as_text=True)

    assert "1 new since" in html
    newer, older = html.split("A newer thread")[0], html.split("A newer thread")[1]
    assert ">New</span>" in newer
    assert ">New</span>" not in older
    assert older.index("Read already") < older.index("An older thread")


def test_marking_my_feed_read_leaves_nothing_new(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = _news_then_older_news(db, community1)

    with client_login(client, member):
        response = client.post(url_for("main.feed_read"), data={"kind": "wiki"})
        html = client.get(url_for("main.home")).get_data(as_text=True)

    assert response.location == url_for("main.home", kind="wiki")
    assert "A newer thread" in html
    assert ">New</span>" not in html


def test_what_is_new_is_said_in_my_language(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = _news_then_older_news(db, community1)
    member.locale = "fr"
    db.session.commit()

    with client_login(client, member):
        html = unescape(client.get(url_for("main.home")).get_data(as_text=True))

    assert ">Nouveau</span>" in html
    assert "1 nouveauté depuis" in html
    assert "Tout marquer comme lu" in html


def test_my_feed_starts_a_discussion_in_one_of_my_communities(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    with client_login(client, community1.test_user):
        html = client.get(url_for("main.home")).get_data(as_text=True)

    composer = html.split('class="ads-card__body sbe-composer"')[1].split("</details>")[
        0
    ]
    new_thread = url_for("forum.new_thread", community_id=community1.slug)
    assert f'href="{new_thread}"' in composer


def test_a_communitys_home_starts_a_discussion_or_an_event_in_it(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = community1.test_user
    here = {"community_id": community1.slug}

    with client_login(client, member):
        html = client.get(url_for("wall.index", **here)).get_data(as_text=True)

    composer = html.split('class="ads-card__body sbe-composer"')[1].split("</div>")[0]
    assert f'href="{url_for("forum.new_thread", **here)}"' in composer
    assert f'href="{url_for("calendar.new_event", **here)}"' in composer


def test_my_communities_say_how_much_is_new_in_each(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    member = _news_then_older_news(db, community1)

    with client_login(client, member):
        html = client.get(url_for("main.home")).get_data(as_text=True)

    mine = html.split('id="mine"')[1].split("</section>")[0]
    assert f"<strong>{community1.name}</strong>" in mine
    assert '<span class="ads-badge ads-tone-info" aria-hidden="true">1</span>' in mine
    assert '<span class="sbe-sr-only">1 new</span>' in mine
