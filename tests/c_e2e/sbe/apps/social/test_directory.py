# Copyright (c) 2012-2026, Abilian SAS

"""The directory: whom I share a community with first, and those communities; and
a person's profile.

Its filter and sort are in `tests/c_e2e/sbe/apps/communities/test_listings.py`.
"""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MEMBER
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _person(db: SQLAlchemy, first: str, last: str) -> User:
    user = User(
        first_name=first,
        last_name=last,
        email=f"{uuid4().hex}@example.com",
        password=uuid4().hex,
        can_login=True,
    )
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def neighbour(community1: Community, db: SQLAlchemy) -> User:
    """Someone in the test user's community; and a stranger, in none of theirs."""
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MEMBER)
    neighbour = _person(db, "Nadia", "Benali")
    community1.set_membership(neighbour, MEMBER)
    _person(db, "Sam", "Stranger")
    db.session.commit()
    return neighbour


def _directory(client: FlaskClient, user: User, **args) -> str:
    with client_login(client, user):
        response = client.get(url_for("social.users", **args))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def _rows(html: str) -> str:
    return html.split("<tbody>")[1].split("</tbody>", maxsplit=1)[0]


def _row(rows: str, name: str) -> str:
    """The row of the person named."""
    return next(row for row in rows.split("<tr>") if f">{name}</strong>" in row)


def test_the_directory_lists_whom_i_share_a_community_with_first(
    neighbour: User, community1: Community, client: FlaskClient
) -> None:
    html = _directory(client, community1.test_user)

    rows = _rows(html)
    assert "Nadia Benali" in rows
    assert "Sam Stranger" not in rows
    nadia = _row(rows, "Nadia Benali")
    assert f'aria-label="{community1.name}"' in nadia
    assert 'aria-current="page">My communities' in html


def test_everyone_is_one_click_away(
    neighbour: User, community1: Community, client: FlaskClient
) -> None:
    html = _directory(client, community1.test_user, who="all")

    rows = _rows(html)
    assert "Nadia Benali" in rows
    assert "Sam Stranger" in rows
    stranger = _row(rows, "Sam Stranger")
    assert "sbe-tile" not in stranger


def test_a_profile_shows_only_the_communities_in_common(
    neighbour: User,
    community1: Community,
    community2: Community,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    community2.set_membership(neighbour, MEMBER)
    db.session.commit()

    with client_login(client, community1.test_user):
        response = client.get(url_for("social.user", user_id=neighbour.id))

    html = unescape(response.get_data(as_text=True))
    assert response.status_code == 200
    shared = html.split('id="communities"')[1].split("</section>")[0]
    assert "Communities in common" in shared
    assert community1.name in shared
    assert community2.name not in shared
    assert "Edit the profile" not in html


def test_one_edits_ones_own_profile(neighbour: User, client: FlaskClient) -> None:
    with client_login(client, neighbour):
        response = client.get(url_for("social.user", user_id=neighbour.id))

    html = unescape(response.get_data(as_text=True))
    assert url_for("social.user_edit", user_id=neighbour.id) in html
    assert "Communities</h2>" in html
