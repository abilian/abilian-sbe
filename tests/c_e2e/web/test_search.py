# Copyright (c) 2012-2024, Abilian SAS

"""Both search endpoints, for members and anonymous visitors; what the results page
says of its results.

Nothing exercised these before. The live endpoint in particular was only ever
reached from the navbar, and the typeahead widget that used to drive it bailed
out before making the request whenever the index was empty -- which, on a fresh
instance, is always.
"""

from __future__ import annotations

from datetime import datetime
from html import unescape
from typing import TYPE_CHECKING

import pytest
import whoosh.query as wq
from flask import url_for
from flask_login import current_user

from abilian.sbe.apps.communities.models import MEMBER
from abilian.sbe.apps.communities.search import filter_user_communities
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.forum.models import Thread
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@pytest.mark.parametrize("endpoint", ["search.search_main", "search.live"])
def test_search_works_for_a_member(
    endpoint: str, community1: Community, app: Application, client: FlaskClient
) -> None:
    ensure_services_started(["security", "indexing"])

    with client_login(client, community1.test_user):
        response = client.get(url_for(endpoint, q="test"))

    assert response.status_code == 200


@pytest.mark.parametrize("endpoint", ["search.search_main", "search.live"])
def test_search_sends_an_anonymous_visitor_to_login(
    endpoint: str, community1: Community, app: Application, client: FlaskClient
) -> None:
    """Everything worth finding is members-only, so search is too."""
    ensure_services_started(["security", "indexing"])

    response = client.get(url_for(endpoint, q="test"))

    assert response.status_code == 302
    assert "/login" in response.location


def test_live_search_answers_with_json(
    community1: Community, app: Application, client: FlaskClient
) -> None:
    ensure_services_started(["security", "indexing"])

    with client_login(client, community1.test_user):
        # JSONView content-negotiates: it serves HTML unless JSON is asked
        # for, which is what livesearch.js sends.
        response = client.get(
            url_for("search.live", q="test"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    assert "results" in response.get_json()


def test_the_community_filter_hides_community_content_from_anonymous(
    app: Application, community1: Community
) -> None:
    """Community content is members-only, and an anonymous visitor is a member
    of nothing, so what comes back is the "not community content" term alone.

    This filter used to read `g.is_manager` and `current_user` out of the
    request. `g.is_manager` is only set once flask-login has loaded a user, so
    on an anonymous request it was absent and reading it bare raised
    AttributeError -- which took both search endpoints down. Taking the subject
    as an argument makes that unrepresentable rather than guarded.
    """
    with app.test_request_context("/search?q=test"):
        query = filter_user_communities(current_user)

    assert query == wq.Term("is_community_content", False)


@pytest.fixture
def indexed(
    community1: Community,
    community2: Community,
    db: SQLAlchemy,
    monkeypatch: pytest.MonkeyPatch,
) -> User:
    """A thread on the budget in each community, and a document in the first, indexed
    as they are saved; a member of both, who finds them."""
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    ensure_services_started(["security", "indexing"])
    member = community1.test_user
    community2.set_membership(member, MEMBER)
    for community, title in ((community1, "Budget 2027"), (community2, "Budget vote")):
        thread = Thread(title=title, community=community)
        thread.create_post(body_html="<p>The figures.</p>")
        db.session.add(thread)
    community1.folder.create_document(title="Budget 2027.txt")
    db.session.commit()
    return member


def _results(client: FlaskClient, user: User, **args) -> str:
    with client_login(client, user):
        response = client.get(url_for("search.search_main", q="budget", **args))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def _links(html: str) -> list[str]:
    """Where the results lead, in order."""
    return [part.split('"')[0] for part in html.split('sbe-result__title" href="')[1:]]


def test_results_say_their_kind_and_their_community(
    indexed: User, community1: Community, community2: Community, client: FlaskClient
) -> None:
    html = _results(client, indexed)

    assert "3 results" in html
    assert "Discussions (2)" in html
    assert "Documents (1)" in html
    assert len(_links(html)) == 3
    by_community = html.split('id="elsewhere"')[1]
    assert f'{community1.name}</span><span class="ads-muted">2' in by_community
    assert f'{community2.name}</span><span class="ads-muted">1' in by_community


def test_a_search_in_a_community_says_what_is_elsewhere(
    indexed: User, community1: Community, community2: Community, client: FlaskClient
) -> None:
    html = _results(client, indexed, community=community1.slug)

    assert "2 results" in html
    assert all(f"/{community1.slug}/" in link for link in _links(html))
    assert "Search everywhere (3)" in html
    elsewhere = html.split('id="elsewhere"')[1]
    assert community2.name in elsewhere
    assert community1.name not in elsewhere


def test_a_kind_narrows_the_results_and_keeps_its_count(
    indexed: User, community1: Community, client: FlaskClient
) -> None:
    html = _results(client, indexed, object_type=[Document.entity_type])

    assert len(_links(html)) == 1
    assert "/docs/doc/" in _links(html)[0]
    assert "Discussions (2)" in html


def test_a_period_leaves_out_what_changed_before_it(
    indexed: User, community1: Community, client: FlaskClient, db: SQLAlchemy
) -> None:
    old = Thread(title="Budget 2019", community=community1)
    old.create_post(body_html="<p>Long ago.</p>")
    old.created_at = old.updated_at = datetime(2019, 3, 1)
    db.session.add(old)
    db.session.commit()

    everything = _results(client, indexed)
    recent = _results(client, indexed, since="30d")

    assert "2019" in everything
    assert "2019" not in recent.split('class="ads-list sbe-results"')[1]


def test_a_search_with_nothing_in_its_community_still_says_where_it_looked(
    indexed: User, community1: Community, client: FlaskClient
) -> None:
    with client_login(client, indexed):
        response = client.get(
            url_for("search.search_main", q="nowhere", community=community1.slug)
        )

    html = unescape(response.get_data(as_text=True))
    assert "0 results in" in html
    assert community1.name in html.split('class="ads-chip')[1]
