# Copyright (c) 2012-2026, Abilian SAS

"""The members page counts each member's threads and last activity in queries,
without loading the threads, nor anyone's photo."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import sqlalchemy as sa
from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from tests.forum_util import started_thread
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _person(db: SQLAlchemy, community: Community, last: str, role) -> User:
    user = User(
        first_name="Ann",
        last_name=last,
        email=f"{uuid4().hex}@example.com",
        password=uuid4().hex,
        can_login=True,
    )
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    return user


@pytest.fixture
def statements(db: SQLAlchemy) -> Iterator[list[str]]:
    """The SQL statements run while the test runs."""
    seen: list[str] = []

    def record(conn, cursor, statement, *args) -> None:
        seen.append(statement)

    sa.event.listen(db.engine, "before_cursor_execute", record)
    yield seen
    sa.event.remove(db.engine, "before_cursor_execute", record)


def test_each_member_s_threads_are_counted_without_loading_them(
    community1: Community, db: SQLAlchemy, client: FlaskClient, statements: list
) -> None:
    ensure_services_started(["security"])
    manager = _person(db, community1, "Manager", MANAGER)
    member = _person(db, community1, "Member", MEMBER)
    for title in ("Budget", "Agenda"):
        started_thread(db, community1, member, title)
    db.session.commit()

    with client_login(client, manager):
        statements.clear()
        response = client.get(
            url_for("communities.members", community_id=community1.slug)
        )

    assert response.status_code == 200
    html = unescape(response.get_data(as_text=True))
    (row,) = (row for row in html.split("<tr") if "Ann Member" in row)
    assert '<td class="ads-end ads-col--secondary">2</td>' in row
    thread_queries = [s for s in statements if "JOIN forum_thread" in s]
    assert thread_queries
    assert all("count(" in s for s in thread_queries)
    assert not [s for s in statements if "user_photo" in s]
