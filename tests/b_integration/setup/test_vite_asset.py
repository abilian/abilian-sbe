# Copyright (c) 2012-2024, Abilian SAS

"""Tests for the Vite asset tag helper.

The production branch of this helper once emitted `/static/vite/...`, a path
nothing serves, and no test noticed because the suite runs with DEBUG=True and
only ever exercised the dev-server branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from abilian.setup.extensions import VITE_DEV_SERVER, vite_asset

if TYPE_CHECKING:
    from abilian.app import Application


def test_dev_mode_points_at_the_vite_dev_server(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    with app.test_request_context():
        monkeypatch.setitem(app.config, "DEBUG", True)
        tag = vite_asset("src/charts-styles.css")

    assert VITE_DEV_SERVER in tag
    assert "src/charts-styles.css" in tag


def test_dev_server_address_is_configurable(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    with app.test_request_context():
        monkeypatch.setitem(app.config, "DEBUG", True)
        monkeypatch.setitem(app.config, "VITE_DEV_SERVER", "http://elsewhere:1234")
        tag = vite_asset("src/main.js")

    assert "http://elsewhere:1234/src/main.js" in tag


def test_production_mode_uses_the_served_static_route(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    with app.test_request_context():
        monkeypatch.setitem(app.config, "DEBUG", False)
        css = vite_asset("src/charts-styles.css")
        js = vite_asset("src/main.js")

    # Must match where `make front` writes and what abilian_sbe_static serves.
    # The trailing `?v=` is the cache-busting stamp added to every static URL.
    assert 'href="/static/abilian/sbe/vite/charts-styles.css?v=' in css
    assert 'src="/static/abilian/sbe/vite/main.js?v=' in js


def test_css_and_js_get_the_right_tag(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    with app.test_request_context():
        monkeypatch.setitem(app.config, "DEBUG", False)
        assert vite_asset("src/charts-styles.css").startswith("<link")
        assert 'rel="stylesheet"' in vite_asset("src/charts-styles.css")
        assert vite_asset("src/main.js").startswith("<script")
        assert 'type="module"' in vite_asset("src/main.js")


def test_unknown_extension_raises(app: Application) -> None:
    """A silent "" here means a missing stylesheet nobody notices."""
    with app.test_request_context(), pytest.raises(ValueError, match=r"expected \.css"):
        vite_asset("src/mystery.woff2")


def test_dev_css_is_requested_as_plain_css(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dev server answers a bare .css with a JS module, which the browser
    refuses for a stylesheet -- the whole page then renders unstyled."""
    with app.test_request_context():
        monkeypatch.setitem(app.config, "DEBUG", True)
        tag = vite_asset("src/charts-styles.css")

    assert "src/charts-styles.css?direct" in tag
    assert 'rel="stylesheet"' in tag


def test_production_css_has_no_dev_query(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    with app.test_request_context():
        monkeypatch.setitem(app.config, "DEBUG", False)
        tag = vite_asset("src/charts-styles.css")

    assert "?direct" not in tag
