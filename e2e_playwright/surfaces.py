# Copyright (c) 2012-2024, Abilian SAS

"""Every kind of page, for the checks that apply to all of them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

COMMUNITY = "e2e-community"
_C = f"/communities/{COMMUNITY}"

PATHS = (
    "/communities/",
    f"{_C}/",
    f"{_C}/docs/",
    f"{_C}/wiki/",
    f"{_C}/wiki/new",
    f"{_C}/forum/",
    f"{_C}/forum/new_thread/",
    f"{_C}/members",
    f"{_C}/members/wizard/step1",
    f"{_C}/settings",
    "/communities/new",
    # Mon fil, the home page: on the Abilian Design System.
    "/",
    "/social/users/",
    "/social/groups/",
    "/preferences/",
    "/search/?q=e2e",
    "/admin/dashboard",
    "/admin/users",
    "/admin/users/new",
    "/admin/groups",
    "/admin/audit",
    "/admin/login_sessions",
    "/admin/settings",
    "/admin/sysinfo",
    "/admin/vocabularies",
    "/admin/tags",
)


def all_paths(page: Page, base_url: str) -> list[str]:
    """`PATHS`, and the pages reached through an object's id."""
    links = {
        f"{_C}/docs/": ("#objects-table tbody a", "E2E Sample"),
        f"{_C}/forum/": ("main a, a", "Welcome to the new members"),
        "/admin/groups": ("table a", "E2E Group"),
        "/social/groups/": ("a", "E2E Group"),
        "/admin/users": ("table a", "Paula Picker"),
        "/social/users/": ("a", "Paula Picker"),
    }
    found = []
    for listing, (selector, text) in links.items():
        page.goto(f"{base_url}{listing}", wait_until="networkidle")
        href = page.locator(selector, has_text=text).first.get_attribute("href")
        found.append(href.removeprefix(base_url))
    return [*PATHS, *found]
