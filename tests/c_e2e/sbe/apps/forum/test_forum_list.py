# Copyright (c) 2012-2026, Abilian SAS

"""A community's discussions, on the Abilian Design System."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for

from tests.forum_util import started_thread
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _list(client: FlaskClient, community: Community, user: User, **args) -> str:
    with client_login(client, user):
        response = client.get(
            url_for("forum.index", community_id=community.slug, **args)
        )
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_the_list_shows_the_threads_with_their_unread_posts(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    started_thread(db, community1, community1.test_user, "Budget 2027")

    html = _list(client, community1, community1.test_user)

    assert "Budget 2027" in html
    assert "New discussion" in html
    assert "ads/ads.css" in html


def test_a_thread_never_opened_counts_its_replies_as_new(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    author = community1.test_user
    started_thread(db, community1, author, "Budget 2027", replies=2)

    html = _list(client, community1, author)

    assert "2 new" in html


def test_the_filter_keeps_the_threads_with_the_words_in_their_title(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    started_thread(db, community1, community1.test_user, "Budget 2027")
    started_thread(db, community1, community1.test_user, "General assembly")

    html = _list(client, community1, community1.test_user, q="budget")

    assert "Budget 2027" in html
    assert "General assembly" not in html


def test_an_unknown_period_is_a_bad_request(
    app: Application, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    with client_login(client, community1.test_user):
        response = client.get(
            url_for("forum.index", community_id=community1.slug, filter="decade")
        )

    assert response.status_code == 400


def test_the_most_read_this_week_lists_the_recent_threads(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    started_thread(db, community1, community1.test_user, "Budget 2027")

    html = _list(client, community1, community1.test_user, filter="week")

    assert "Budget 2027" in html
