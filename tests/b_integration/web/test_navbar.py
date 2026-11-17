# Copyright (c) 2012-2024, Abilian SAS

"""The admin section is reached from the user menu.

It used to be a second dropdown of its own in the top bar, holding nothing but
the list of panels that every admin page already shows in its own sidebar.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pytest import fixture

from abilian.services.security import ADMIN, security
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy

ADMIN_ENTRY = b"action-navigation-user-admin"
#: A page still on the old frame: `/` has moved to the Abilian Design System,
#: whose bar `tests/c_e2e/sbe/apps/main/test_home.py` covers.
LEGACY_PAGE = "/communities/"


def _navbar(response) -> str:
    match = re.search(r"<nav .*?</nav>", response.data.decode(), re.DOTALL)
    assert match, "no navbar in the response"
    return match.group(0)


@fixture
def logged_in(client: FlaskClient, user: User, db: SQLAlchemy) -> FlaskClient:
    # `has_role` answers True for everyone while the service is stopped, which
    # would make both of these tests pass whatever the condition said.
    ensure_services_started(["security"])
    with client.session_transaction() as session:
        session["_user_id"] = user.id
    return client


@fixture
def logged_in_admin(logged_in: FlaskClient, user: User, db: SQLAlchemy) -> FlaskClient:
    # The `admin_user` fixture only sets `is_admin` on the model, which
    # `has_role` does not consult; the role has to be granted.
    security.grant_role(user, ADMIN)
    db.session.flush()
    return logged_in


def test_an_admin_sees_the_admin_entry(logged_in_admin: FlaskClient) -> None:
    response = logged_in_admin.get(LEGACY_PAGE)

    assert response.status_code == 200
    assert ADMIN_ENTRY in response.data
    assert b'href="/admin/' in response.data


def test_an_ordinary_user_does_not(logged_in: FlaskClient) -> None:
    response = logged_in.get(LEGACY_PAGE)

    assert response.status_code == 200
    assert ADMIN_ENTRY not in response.data


def test_the_user_name_is_not_shown_beside_the_avatar(
    logged_in: FlaskClient, user: User
) -> None:
    """The avatar identifies the user; the name repeated it.

    It stays as the button's accessible name, because the avatar <img> has no
    alt text and the menu would otherwise be unnamed for a screen reader.
    """
    navbar = _navbar(logged_in.get(LEGACY_PAGE))
    hidden = f'<span class="sr-only">{user.name}</span>'

    # Rendered twice -- the desktop bar and the mobile menu -- and every
    # occurrence of the name must be one of these.
    assert hidden in navbar
    assert navbar.count(user.name) == navbar.count(hidden)


def test_the_avatar_carries_no_chevron(logged_in: FlaskClient) -> None:
    """The avatar is affordance enough; the wedge beside it was noise."""
    navbar = _navbar(logged_in.get(LEGACY_PAGE))
    # The hamburger button comes first in the markup and legitimately has an
    # svg, so match the one holding the avatar.
    triggers = [
        b
        for b in re.findall(r"<button\b.*?</button>", navbar, re.DOTALL)
        if "img" in b and "avatar" in b
    ]

    assert triggers, "expected a menu trigger holding the avatar"
    for trigger in triggers:
        assert "<svg" not in trigger


def test_the_admin_dropdown_is_gone(logged_in_admin: FlaskClient) -> None:
    """The whole `navigation:admin` group is no longer rendered in the bar."""
    response = logged_in_admin.get(LEGACY_PAGE)

    assert b"action-navigation-admin" not in response.data
