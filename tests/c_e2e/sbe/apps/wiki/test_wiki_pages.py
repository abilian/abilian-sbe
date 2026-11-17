# Copyright (c) 2012-2026, Abilian SAS

"""A wiki page's revisions, as the views write them.

The rest of what the views do with a page is in `test_web.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import url_for

from abilian.sbe.apps.communities.models import MEMBER
from abilian.sbe.apps.wiki.models import WikiPage
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@pytest.fixture
def member(community1: Community, db: SQLAlchemy) -> User:
    """A member of a community whose wiki has two pages, one edited twice."""
    ensure_services_started(["security"])
    member = community1.test_user
    community1.set_membership(member, MEMBER)
    for title in ("Expenses", "Glossary"):
        page = WikiPage(title=title, body_src="See [[Glossary]] and [[Nowhere]].")
        page.community_id = community1.id
        db.session.add(page)
    db.session.flush()
    expenses = WikiPage.query.filter_by(title="Expenses").one()
    expenses.create_revision(member, "Trains, in second class.", "Trains")
    db.session.commit()
    return member


def test_a_new_page_starts_with_one_revision(
    member: User, community1: Community, client: FlaskClient
) -> None:
    """It had two: an empty one written by the model's constructor, then the text."""
    data = {"title": "Minutes", "body_src": "The minutes.", "__action": "create"}
    with client_login(client, member):
        response = client.post(
            url_for("wiki.page_new", community_id=community1.slug), data=data
        )

    assert response.status_code == 302
    page = WikiPage.query.filter_by(title="Minutes").one()
    assert [(r.number, r.body_src) for r in page.revisions] == [(0, "The minutes.")]
