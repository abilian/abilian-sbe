# Copyright (c) 2012-2024, Abilian SAS

"""Fixtures for the Playwright suite.

These tests exist because the pytest suite cannot see the front end. A page
whose scripts never loaded, whose widgets never initialised, or whose icon font
is missing still returns a perfectly good 200, which is how the Tailwind branch
came to ship with no icons, no DataTables and a dead documents module.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page

E2E_EMAIL = os.environ.get("E2E_EMAIL", "admin@example.com")
E2E_PASSWORD = os.environ.get("E2E_PASSWORD", "e2e-password")

LOGIN_PATH = "/user/login"

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
