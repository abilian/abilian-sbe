# Copyright (c) 2026, Abilian SAS

"""A member's photo or initials lead to their profile, and name them on hover."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MEMBER
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def test_a_member_s_avatar_on_the_community_page_links_to_their_profile(
    community1: Community, client: FlaskClient, db: SQLAlchemy
) -> None:
    ensure_services_started(["security"])
    member = User(
        first_name="Ann",
        last_name="Member",
        email=f"{uuid4().hex}@example.com",
        password=uuid4().hex,
        can_login=True,
    )
    db.session.add(member)
    db.session.flush()
    community1.set_membership(member, MEMBER)
    db.session.commit()

    with client_login(client, member):
        response = client.get(url_for("wall.index", community_id=community1.slug))
        profile = url_for("social.user", user_id=member.id)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    members_card = html[html.index('id="people"') :]
    assert f'href="{profile}" aria-label="Ann Member" data-tip="Ann Member"' in (
        members_card
    )
