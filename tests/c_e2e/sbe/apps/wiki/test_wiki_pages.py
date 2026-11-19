# Copyright (c) 2012-2026, Abilian SAS

"""The wiki on the Abilian Design System: a page with the wiki's pages beside it, its
history, a comparison, and the form that writes it.

What the views do with a page (creating, editing, attachments) is in `test_web.py`.
"""

from __future__ import annotations

from html import unescape
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


def _get(client: FlaskClient, user: User, endpoint: str, community: Community, **kw):
    with client_login(client, user):
        response = client.get(url_for(endpoint, community_id=community.slug, **kw))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def test_a_page_has_the_wikis_pages_beside_it(
    member: User, community1: Community, client: FlaskClient
) -> None:
    html = _get(client, member, "wiki.page", community1, title="Glossary")

    pages = html.split('id="wiki-pages"')[1].split("</nav>")[0]
    assert "Expenses" in pages
    assert 'aria-current="page"><svg' in pages
    current = pages.split('aria-current="page"')[1].split("</a>")[0]
    assert "Glossary" in current
    # A link to a page not written yet is marked so.
    assert 'class="wikilink new"' in html


def test_the_history_ticks_the_latest_two_revisions(
    member: User, community1: Community, client: FlaskClient
) -> None:
    html = _get(client, member, "wiki.page_changes", community1, title="Expenses")

    assert 'name="rev1" checked' in html
    assert 'name="rev0" checked' in html
    assert "Trains" in html


def test_a_comparison_marks_what_went_and_what_came(
    member: User, community1: Community, client: FlaskClient
) -> None:
    html = _get(
        client,
        member,
        "wiki.page_compare",
        community1,
        title="Expenses",
        rev0="on",
        rev1="on",
    )

    assert "sbe-diff__line sbe-diff__line--del" in html
    assert "sbe-diff__line sbe-diff__line--add" in html
    assert "Trains, in second class." in html


def test_the_form_keeps_what_the_server_reads(
    member: User, community1: Community, client: FlaskClient
) -> None:
    html = _get(client, member, "wiki.page_edit", community1, title="Expenses")

    form = html.split('id="edit-form"')[1].split("</form>")[0]
    for field in (
        'name="title"',
        'name="body_src"',
        'name="message"',
        'name="page_id"',
        'name="last_revision_id"',
    ):
        assert field in form
    assert 'name="__action" value="edit"' in form


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


def test_a_page_runs_no_script_its_writer_put_in(
    member: User, community1: Community, client: FlaskClient, db: SQLAlchemy
) -> None:
    page = WikiPage(
        title="Trap",
        body_src=(
            "## Heading\n\n<script>alert(1)</script>\n\n"
            '<img src="x.png" onerror="alert(2)"> [here](javascript:alert(3))'
        ),
    )
    page.community_id = community1.id
    db.session.add(page)
    db.session.commit()

    with client_login(client, member):
        html = client.get(
            url_for("wiki.page", community_id=community1.slug, title="Trap")
        ).get_data(as_text=True)

    body = html.split('class="ads-card__body ads-prose">')[1].split("</div>")[0]
    assert "<script" not in body
    assert "onerror" not in body
    assert "javascript:" not in body
    assert '<h2 id="heading">Heading</h2>' in body
