# Copyright (c) 2012-2026, Abilian SAS

"""A thread's page, on the Abilian Design System."""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.sbe.apps.communities.models import MANAGER
from abilian.web.util import url_for
from tests.forum_util import started_thread
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community
    from abilian.sbe.apps.forum.models import Thread


def _page(client: FlaskClient, thread: Thread, user: User) -> str:
    with client_login(client, user):
        response = client.get(url_for(thread))
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_a_thread_shows_its_posts_and_the_reply_form(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    thread = started_thread(db, community1, community1.test_user, "Budget 2027", 1)

    html = _page(client, thread, community1.test_user)

    assert "Budget 2027" in html
    assert html.count("Agreed.") == 1
    assert 'id="reply"' in html
    assert "data-richtext" in html
    # The app's scripts, for the editor and the uploads, without Tailwind.
    assert "main.js" in html
    assert "styles.css" not in html


def test_unread_posts_come_after_a_divider_until_read(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    thread = started_thread(db, community1, community1.test_user, "Budget 2027", 2)

    first = _page(client, thread, community1.test_user)
    second = _page(client, thread, community1.test_user)

    assert 'id="new"' in first
    assert "2 new messages" in first
    assert 'id="new"' not in second


def test_a_member_does_not_moderate(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    thread = started_thread(db, community1, community1.test_user, "Budget 2027")

    html = _page(client, thread, community1.test_user)

    assert "Close the discussion" not in html
    assert 'id="modal-delete"' not in html


def test_a_manager_closes_and_deletes(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    manager = community1.test_user
    community1.set_membership(manager, MANAGER)
    thread = started_thread(db, community1, manager, "Budget 2027")

    html = _page(client, thread, manager)

    assert "Close the discussion" in html
    assert 'data-modal-open="#modal-delete"' in html
    assert 'id="modal-delete"' in html


def test_a_closed_thread_takes_no_reply(
    app: Application, db: SQLAlchemy, client: FlaskClient, community1: Community
) -> None:
    ensure_services_started(["security"])
    thread = started_thread(db, community1, community1.test_user, "Budget 2027")
    thread.closed = True
    db.session.commit()

    html = _page(client, thread, community1.test_user)

    assert 'id="reply"' not in html
    assert "it takes no more replies" in html
