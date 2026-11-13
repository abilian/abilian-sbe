# Copyright (c) 2012-2024, Abilian SAS

"""The menu offers a community manager what the views behind it allow.

Actions are authorization too: an `Action`'s `condition` decides whether a
button or tab renders, so a condition that asks a different question from the
route guard behind it produces one of two bugs -- a button that 403s, or a
capability with no door to it.

Both of these were the second kind. The Settings tab asked
`current_user.has_role("admin")` while `CommunityEdit` is `@can_manage`, so a
community manager could reach the settings page only by typing its URL. Forum
moderation -- delete, close and reopen a thread -- asked
`has_role(current_user, ADMIN, object=thread)`, which is the site-wide answer
because nothing ever grants a role on a Thread; so the manager of a community
could not moderate its own forum, and only a site admin could.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for
from pytest import fixture

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, READER
from abilian.sbe.apps.forum.models import Thread
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _member(db: SQLAlchemy, community: Community, email: str, role) -> User:
    ensure_services_started(["security"])
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.flush()
    return user


@fixture
def manager(db: SQLAlchemy, community1: Community) -> User:
    return _member(db, community1, "manager@example.com", MANAGER)


@fixture
def reader(db: SQLAlchemy, community1: Community) -> User:
    return _member(db, community1, "reader@example.com", READER)


@fixture
def thread(db: SQLAlchemy, community1: Community) -> Thread:
    """One thread with one post: the per-thread actions do not render on an
    empty forum, and a post with no owner cannot be rendered at all."""
    author = community1.test_user
    t = Thread(title="A conversation", community=community1)
    t.creator = t.owner = author
    post = t.create_post(body_html="<p>hello</p>")
    post.creator = post.owner = author
    db.session.add(t)
    db.session.commit()
    return t


def _page(client: FlaskClient, url: str) -> str:
    response = client.get(url, follow_redirects=True)
    assert response.status_code == 200, f"{url} returned {response.status_code}"
    return response.get_data(as_text=True)


# --- the Settings tab --------------------------------------------------------


def test_a_manager_is_offered_the_settings_tab(
    community1: Community, manager: User, client: FlaskClient, app: Application
) -> None:
    settings = url_for("communities.settings", community_id=community1.slug)

    with client_login(client, manager):
        page = _page(
            client, url_for("communities.community", community_id=community1.slug)
        )

    assert settings in page, (
        "a manager may edit the settings but is not shown the way in"
    )


def test_a_plain_member_is_not(
    community1: Community, reader: User, client: FlaskClient, app: Application
) -> None:
    settings = url_for("communities.settings", community_id=community1.slug)

    with client_login(client, reader):
        page = _page(
            client, url_for("communities.community", community_id=community1.slug)
        )

    assert settings not in page


# --- forum moderation --------------------------------------------------------

#: Rendered by the close/reopen actions, which share one endpoint.
CLOSE_ACTION = 'value="close"'


def test_a_manager_can_moderate_their_forum(
    community1: Community,
    thread: Thread,
    manager: User,
    client: FlaskClient,
    app: Application,
) -> None:
    with client_login(client, manager):
        page = _page(
            client,
            url_for("forum.thread", community_id=community1.slug, thread_id=thread.id),
        )

    assert CLOSE_ACTION in page, "no way to close a thread in a forum they manage"


def test_a_plain_member_cannot_moderate(
    community1: Community,
    thread: Thread,
    reader: User,
    client: FlaskClient,
    app: Application,
) -> None:
    with client_login(client, reader):
        page = _page(
            client,
            url_for("forum.thread", community_id=community1.slug, thread_id=thread.id),
        )

    assert CLOSE_ACTION not in page


# --- the "Create new community" gate -----------------------------------------


def test_only_a_site_admin_is_offered_a_new_community(
    db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """`community/home.html` asks `is_site_admin()` by name.

    It read a passed-in `is_admin` before, which was also the name
    `social/group.html` used for a *group-scoped* question -- one name, two
    producers, two meanings, which is exactly how `g.is_manager` went wrong.
    """
    from abilian.services import security_service
    from abilian.services.security import ADMIN

    ensure_services_started(["security"])
    plain = User(email="plain@example.com", password="test", can_login=True)  # noqa: S106
    admin = User(email="site-admin@example.com", password="test", can_login=True)  # noqa: S106
    db.session.add_all([plain, admin])
    db.session.flush()
    security_service.grant_role(admin, ADMIN)
    db.session.flush()

    new_url = url_for("communities.new")

    with client_login(client, plain):
        assert new_url not in _page(client, url_for("communities.index"))

    with client_login(client, admin):
        assert new_url in _page(client, url_for("communities.index"))
