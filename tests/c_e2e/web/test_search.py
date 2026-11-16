# Copyright (c) 2012-2024, Abilian SAS

"""Both search endpoints, for members and anonymous visitors.

Nothing exercised these before. The live endpoint in particular was only ever
reached from the navbar, and the typeahead widget that used to drive it bailed
out before making the request whenever the index was empty -- which, on a fresh
instance, is always.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import whoosh.query as wq
from flask import url_for
from flask_login import current_user

from abilian.sbe.apps.communities.search import filter_user_communities
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
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
