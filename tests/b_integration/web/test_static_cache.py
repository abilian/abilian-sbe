# Copyright (c) 2012-2024, Abilian SAS

"""Tests for static asset caching.

Flask sends `Cache-Control: no-cache` for static files unless told otherwise,
so every page view revalidated all ~35 vendored assets. Caching them is only
safe if the URL changes when the file does, hence the `v=` stamp.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from flask import url_for

from abilian.app import _asset_version

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application


def test_static_urls_are_stamped_with_a_version(app: Application) -> None:
    with app.test_request_context():
        url = url_for("abilian_static", filename="highlightjs/init.js")

    assert "?v=" in url, url


def test_the_stamp_follows_the_file(tmp_path) -> None:
    """A changed file must get a new stamp, or upgrades serve stale assets."""
    asset = tmp_path / "thing.js"
    asset.write_text("// v1")

    first = _asset_version(str(tmp_path), "thing.js", debug=True)
    os.utime(asset, (0, 0))
    second = _asset_version(str(tmp_path), "thing.js", debug=True)

    assert first
    assert second
    assert first != second


def test_an_absent_file_has_no_stamp(tmp_path) -> None:
    assert _asset_version(str(tmp_path), "nope.js", debug=True) is None


def test_a_directory_has_no_stamp(tmp_path) -> None:
    """A directory's URL is a base that file names are appended to, as the PDF
    viewer does: `dir/?v=...` + `file` is no URL at all."""
    (tmp_path / "pdfjs").mkdir()
    assert _asset_version(str(tmp_path), "pdfjs/", debug=True) is None


def test_traversal_is_refused(tmp_path) -> None:
    assert _asset_version(str(tmp_path), "../secret.js", debug=True) is None


def test_a_missing_file_does_not_break_url_for(app: Application) -> None:
    """url_for must still work; the request itself can 404."""
    with app.test_request_context():
        url = url_for("abilian_static", filename="does/not/exist.js")

    assert url.endswith("does/not/exist.js")


def test_static_responses_are_cacheable(app: Application, client: FlaskClient) -> None:
    with app.test_request_context():
        url = url_for("abilian_static", filename="highlightjs/init.js")

    response = client.get(url)

    assert response.status_code == 200
    assert response.cache_control.max_age
    assert response.cache_control.max_age > 3600
    # Without `immutable` the browser revalidates on a plain reload, even
    # though the URL is versioned and the answer can only ever be 304.
    assert response.cache_control.immutable


def test_static_responses_do_not_vary_on_cookie(
    app: Application, client: FlaskClient
) -> None:
    """`Vary: Cookie` keys the cached asset by the session cookie.

    The access check reads current_user, so Flask stamps the header in
    save_session. Since the session cookie is re-signed as the user browses,
    every page view missed the cache and refetched the whole asset set.
    """
    with app.test_request_context():
        url = url_for("abilian_static", filename="highlightjs/init.js")

    response = client.get(url)

    assert "Cookie" not in (response.headers.get("Vary") or "")


def test_ordinary_pages_still_vary_on_cookie(client: FlaskClient) -> None:
    """The exemption must not leak to responses that really are per-user."""
    response = client.get("/")

    assert "Cookie" in (response.headers.get("Vary") or "")
