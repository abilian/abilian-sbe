# Copyright (c) 2026, Abilian SAS

"""The communities in the administration: every one, whoever is in it, with its
managers; filtered by name."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER
from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _page(client: FlaskClient, admin: User, **args) -> str:
    with client_login(client, admin):
        response = client.get(url_for("admin.communities", **args))
    assert response.status_code == 200
    table = response.get_data(as_text=True).split('id="communities-table"')[1]
    return unescape(table)


def test_an_administrator_sees_every_community_and_its_managers(
    client: FlaskClient,
    admin_user: User,
    community1: Community,
    community2: Community,
    db: SQLAlchemy,
) -> None:
    manager = User(
        first_name="Ann",
        last_name="Manager",
        email=f"{uuid4().hex}@example.com",
        can_login=True,
    )
    db.session.add(manager)
    community1.set_membership(manager, MANAGER)
    db.session.commit()

    table = _page(client, admin_user)

    assert community1.name in table
    assert community2.name in table
    row = table.split(community1.name)[1].split("</tr>")[0]
    assert "Ann Manager" in row


def test_the_communities_are_filtered_by_name(
    client: FlaskClient,
    admin_user: User,
    community1: Community,
    community2: Community,
    db: SQLAlchemy,
) -> None:
    db.session.commit()

    table = _page(client, admin_user, q="another")

    assert community2.name in table
    assert community1.name not in table


def test_a_rows_menu_leads_where_an_administrator_may_go(
    client: FlaskClient, admin_user: User, community2: Community, db: SQLAlchemy
) -> None:
    """Into a community the administrator is not a member of."""
    db.session.commit()
    here = {"community_id": community2.slug}

    table = _page(client, admin_user)
    with client_login(client, admin_user):
        settings = client.get(url_for("communities.settings", **here))
        members = client.get(url_for("communities.members", **here))

    assert url_for("communities.settings", **here) in table
    assert (settings.status_code, members.status_code) == (200, 200)
