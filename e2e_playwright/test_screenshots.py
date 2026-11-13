# Copyright (c) 2012-2024, Abilian SAS

"""A few stable regions, compared with approved images.

The other browser tests check that things work; these check that they still
look the way they were approved, which is the part of the Tailwind migration no
other test can hold in place. They run only in the Linux browser container
(`make test-screenshots`); `make update-screenshots` approves the current look.

Text that changes between runs (how long ago the data was seeded) is set to a
fixed value first, so a failure means the layout or the styling moved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Page

#: Seeded by seed.py, which serve.sh runs before starting the app.
COMMUNITY = "e2e-community"


def test_login_page(page: Page, base_url: str, assert_screenshot: Callable) -> None:
    page.goto(f"{base_url}/user/login", wait_until="networkidle")

    assert_screenshot(page, "login")


def test_navbar(logged_in: Page, base_url: str, assert_screenshot: Callable) -> None:
    logged_in.goto(f"{base_url}/communities/", wait_until="networkidle")

    assert_screenshot(logged_in.locator("nav[role=navigation]"), "navbar")


def test_folder_listing(
    logged_in: Page, base_url: str, assert_screenshot: Callable
) -> None:
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )

    table = logged_in.locator("#objects-table")
    # Age says how long ago seed.py ran, so it is set to one fixed value.
    ages = table.locator("tbody td:nth-child(5)")
    assert ages.count() == 2, "the Age column has moved"
    ages.evaluate_all("cells => cells.forEach(cell => cell.textContent = '2 minutes')")

    assert_screenshot(table, "folder-listing")


def test_admin_users_table(
    logged_in: Page, base_url: str, assert_screenshot: Callable
) -> None:
    # Tall enough for the whole table: scrolled to fit, it would have the sticky
    # navbar across its header.
    logged_in.set_viewport_size({"width": 1280, "height": 1800})
    logged_in.goto(f"{base_url}/admin/users", wait_until="networkidle")

    table = logged_in.locator("#users-table")
    # Whoever has logged in shows when, and that is now: the test's own login.
    last_connection = table.locator("tbody td:last-child")
    last_connection.evaluate_all(
        "cells => cells.forEach(cell => {"
        "  if (!cell.textContent.includes('Never')) cell.textContent = 'Nov 5, 2026';"
        "})"
    )

    assert_screenshot(table, "admin-users")


def test_new_folder_modal(
    logged_in: Page, base_url: str, assert_screenshot: Callable
) -> None:
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )
    logged_in.locator('[data-modal-open="#modal-new-folder"]').first.click()

    # The <dialog> itself spans the viewport; the panel is what was designed.
    assert_screenshot(
        logged_in.locator("#modal-new-folder .modal-content"), "new-folder-modal"
    )
