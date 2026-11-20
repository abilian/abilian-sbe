# Copyright (c) 2012-2024, Abilian SAS

"""Smoke tests for the main pages.

The rest of the suite exercises models, services and views in isolation, so it
stays green even when the rendered page is unusable. These tests render the
pages a user actually visits and check that the layout came out whole, which is
the safety net the Bootstrap -> Tailwind migration needs.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from flask import url_for

from abilian.services import security_service
from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.sbe.apps.communities.models import Community

#: Pages scoped to a community, keyed by endpoint.
COMMUNITY_PAGES = [
    "wall.index",
    "documents.index",
    "forum.index",
    "wiki.index",
]

#: Pages that don't need a community.
GLOBAL_PAGES = [
    "communities.index",
    "main.home",
    "preferences.index",
]


def assert_page_is_whole(response) -> None:
    """A 200 is not enough: check the layout actually rendered."""
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "<title>" in html, "no <title>: base template did not render"
    assert "</body>" in html, "truncated page: rendering blew up mid-template"
    assert 'rel="stylesheet"' in html, "no stylesheet linked: asset plumbing is broken"


@pytest.mark.parametrize("endpoint", COMMUNITY_PAGES)
def test_community_page_renders(
    endpoint: str, community1: Community, app: Application, client: FlaskClient
) -> None:
    security_service.start()

    with client_login(client, community1.test_user):
        response = client.get(
            url_for(endpoint, community_id=community1.slug), follow_redirects=True
        )

    assert_page_is_whole(response)


@pytest.mark.parametrize("endpoint", GLOBAL_PAGES)
def test_global_page_renders(
    endpoint: str, community1: Community, app: Application, client: FlaskClient
) -> None:
    security_service.start()

    with client_login(client, community1.test_user):
        response = client.get(url_for(endpoint), follow_redirects=True)

    assert_page_is_whole(response)


def test_referenced_assets_resolve_in_production_mode(
    community1: Community, app: Application, client: FlaskClient, monkeypatch
) -> None:
    """Every CSS/JS file the page references must actually be served.

    The suite runs with DEBUG=True, where `vite_asset` points at the Vite dev
    server, so the production branch would otherwise never be exercised -- which
    is how it came to emit `/static/vite/...`, a path nothing serves. The same
    check covers the vendored <script> tags, where a wrong filename is likewise
    invisible server-side.

    Needs the built assets: run `make front` first.
    """
    monkeypatch.setitem(app.config, "DEBUG", False)
    security_service.start()

    def static_urls(endpoint: str) -> list[str]:
        with client_login(client, community1.test_user):
            response = client.get(
                url_for(endpoint, community_id=community1.slug), follow_redirects=True
            )
        html = response.get_data(as_text=True)
        # Static URLs carry a `?v=` cache-busting stamp, so the extension is not
        # the end of the URL.
        return sorted(
            set(
                re.findall(
                    r'(?:href|src)="(/static/[^"]+\.(?:css|js)(?:\?[^"]*)?)"', html
                )
            )
        )

    # Every page is on the Abilian Design System now: the community's home will do.
    ads = static_urls("wall.index")
    assert any("/ads/ads.css" in url for url in ads), "page linked no ADS stylesheet"
    assert any("/vite/" in url for url in ads), "page linked no Vite assets"

    broken = [url for url in ads if client.get(url).status_code != 200]
    assert not broken, f"referenced but not served: {broken}"
