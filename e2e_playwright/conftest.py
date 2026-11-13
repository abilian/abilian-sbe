# Copyright (c) 2012-2024, Abilian SAS

"""Fixtures for the Playwright suite.

These tests exist because the pytest suite cannot see the front end. A page
whose scripts never loaded, whose widgets never initialised, or whose icon font
is missing still returns a perfectly good 200, which is how the Tailwind branch
came to ship with no icons, no DataTables and a dead documents module.
"""

from __future__ import annotations

import io
import os
import pathlib
from typing import TYPE_CHECKING

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Locator, Page

E2E_EMAIL = os.environ.get("E2E_EMAIL", "admin@example.com")
E2E_PASSWORD = os.environ.get("E2E_PASSWORD", "e2e-password")

LOGIN_PATH = "/user/login"

#: Set by Procfile.screenshots: the Linux browser container (browser.sh).
PW_WS_ENDPOINT = os.environ.get("PW_WS_ENDPOINT")
UPDATE_SCREENSHOTS = bool(os.environ.get("E2E_UPDATE_SCREENSHOTS"))

HERE = pathlib.Path(__file__).parent
APPROVED_DIR = HERE / "screenshots"
RESULTS_DIR = HERE / "screenshot-results"

#: The pinned container renders the same page to the same pixels, so any change
#: fails. This only absorbs a channel off by a few, should that ever happen.
PIXEL_TOLERANCE = 8

#: Console noise that says nothing about our own JavaScript.
IGNORED_CONSOLE = (
    "favicon",
    "Failed to load resource: net::ERR_FILE_NOT_FOUND",
)


class JSErrors:
    """Collects uncaught exceptions and console errors for one page."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def record(self, message: str) -> None:
        if not any(noise in message for noise in IGNORED_CONSOLE):
            self.messages.append(message)

    def assert_clean(self, context: str) -> None:
        assert not self.messages, f"JavaScript errors on {context}:\n" + "\n".join(
            f"  - {m}" for m in self.messages
        )


@pytest.fixture(scope="session")
def connect_options() -> dict | None:
    """Use the browser container when there is one, else a local browser."""
    return {"endpoint": PW_WS_ENDPOINT} if PW_WS_ENDPOINT else None


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """The dev server uses a throwaway self-signed certificate."""
    return {**browser_context_args, "ignore_https_errors": True}


@pytest.fixture
def js_errors(page: Page) -> JSErrors:
    """Attach error listeners before any navigation happens."""
    errors = JSErrors()
    page.on("pageerror", lambda exc: errors.record(f"uncaught: {exc}"))
    # Console says only "Failed to load resource"; the URL is what makes it
    # actionable, so record the request itself.
    page.on(
        "requestfailed",
        lambda req: errors.record(f"request failed: {req.url} ({req.failure})"),
    )
    page.on(
        "response",
        lambda res: (
            errors.record(f"HTTP {res.status}: {res.url}")
            if res.status >= 500
            else None
        ),
    )
    page.on(
        "console",
        lambda msg: (
            errors.record(f"console.error: {msg.text}") if msg.type == "error" else None
        ),
    )
    return errors


@pytest.fixture
def logged_in(page: Page, base_url: str, js_errors: JSErrors) -> Page:
    """A page with an authenticated admin session."""
    page.goto(f"{base_url}{LOGIN_PATH}", wait_until="domcontentloaded")

    page.fill('input[name="email"]', E2E_EMAIL)
    page.fill('input[name="password"]', E2E_PASSWORD)
    page.click('button[type="submit"], input[type="submit"]')

    expect(page).not_to_have_url(f"{base_url}{LOGIN_PATH}", timeout=15_000)
    return page


@pytest.fixture
def assert_screenshot() -> Callable[..., None]:
    """Compare a page or element with its approved image in `screenshots/`.

    Only in the browser container: an image taken anywhere else differs from
    the approved one for reasons that have nothing to do with the app. With
    E2E_UPDATE_SCREENSHOTS set, the screenshot becomes the approved image.
    """
    if not PW_WS_ENDPOINT:
        pytest.skip(
            "screenshots are compared in a Linux browser: make test-screenshots"
        )

    def check(target: Page | Locator, name: str) -> None:
        page = getattr(target, "page", target)
        page.evaluate("document.fonts.ready")
        png = target.screenshot(animations="disabled", caret="hide", scale="css")
        approved = APPROVED_DIR / f"{name}.png"
        if UPDATE_SCREENSHOTS:
            APPROVED_DIR.mkdir(exist_ok=True)
            approved.write_bytes(png)
            return
        assert approved.exists(), (
            f"no approved image for {name!r}: run make update-screenshots"
        )

        actual = Image.open(io.BytesIO(png)).convert("RGB")
        expected = Image.open(approved).convert("RGB")
        if actual.size != expected.size:
            changed, reason = None, f"size {actual.size} instead of {expected.size}"
        else:
            changed = ImageChops.difference(actual, expected).point(
                lambda v: 255 if v > PIXEL_TOLERANCE else 0
            )
            if changed.getbbox() is None:
                return
            reason = f"pixels changed in the region {changed.getbbox()}"

        RESULTS_DIR.mkdir(exist_ok=True)
        (RESULTS_DIR / f"{name}-actual.png").write_bytes(png)
        if changed is not None:
            changed.save(RESULTS_DIR / f"{name}-diff.png")
        pytest.fail(
            f"{name}: {reason}; see {RESULTS_DIR.relative_to(HERE.parent)}/. "
            "If the change is intended, run make update-screenshots."
        )

    return check
