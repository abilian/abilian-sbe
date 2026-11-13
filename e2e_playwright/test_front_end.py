# Copyright (c) 2012-2024, Abilian SAS

"""Front-end checks the server-side suite structurally cannot make.

Each of these corresponds to a way the Tailwind branch was broken while pytest
stayed green: scripts dropped from the page, an icon font never shipped, an AMD
shim resolving modules to empty objects.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from conftest import JSErrors
    from playwright.sync_api import Page


def test_home_page_has_no_js_errors(
    page: Page, base_url: str, js_errors: JSErrors
) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    js_errors.assert_clean("the home page")


@pytest.mark.parametrize(
    "path",
    [
        "/social/",
        "/communities/",
        "/preferences/",
        # The dashboard is the only page that loads the uPlot chart entry.
        "/admin/dashboard",
        # A server-rendered table: its filter, sort and pages are plain links.
        "/admin/users",
    ],
)
def test_main_pages_have_no_js_errors(
    logged_in: Page, base_url: str, js_errors: JSErrors, path: str
) -> None:
    """The check that would have caught the whole Phase 2 breakage at once."""
    logged_in.goto(f"{base_url}{path}", wait_until="networkidle")
    js_errors.assert_clean(path)


def test_the_javascript_layer_is_loaded(logged_in: Page, base_url: str) -> None:
    """The bundle ran, and nothing still brings jQuery back in."""
    logged_in.goto(f"{base_url}/social/", wait_until="networkidle")

    assert logged_in.evaluate("typeof window.jQuery") == "undefined"
    assert logged_in.evaluate("typeof window.$") == "undefined"
    assert logged_in.evaluate("typeof window.Alpine") != "undefined", "Alpine missing"


def test_buttons_show_a_pointer_cursor(logged_in: Page, base_url: str) -> None:
    """Tailwind v4's preflight sets `cursor: default` on buttons.

    Only `.btn` re-declared it, so every button outside that component read as
    unclickable. The fix is a base rule, so any button will do as the check.
    """
    logged_in.goto(f"{base_url}/communities/", wait_until="networkidle")

    trigger = logged_in.locator("nav button:has(img.avatar)").first
    cursor = trigger.evaluate("el => getComputedStyle(el).cursor")

    assert cursor == "pointer", f"menu trigger cursor is {cursor!r}"


def test_icon_font_is_applied(logged_in: Page, base_url: str) -> None:
    """`fa fa-*` is used ~147 times; without the font every icon is a blank box."""
    logged_in.goto(f"{base_url}/social/", wait_until="networkidle")

    icon = logged_in.locator("i.fa").first
    assert icon.count() > 0, "no FontAwesome icon on the page to check"

    font = icon.evaluate("el => getComputedStyle(el).fontFamily")
    assert "FontAwesome" in font, f"icon font not applied, got {font!r}"


def test_stylesheet_is_applied(logged_in: Page, base_url: str) -> None:
    """Catches the unstyled page an asset-path mismatch produces."""
    logged_in.goto(f"{base_url}/social/", wait_until="networkidle")

    body_bg = logged_in.evaluate("getComputedStyle(document.body).backgroundColor")
    # Tailwind's preflight sets a background; an unstyled page stays transparent.
    assert body_bg not in ("", "rgba(0, 0, 0, 0)"), (
        f"no stylesheet applied to body, background is {body_bg!r}"
    )


#: Seeded by seed.py, which serve.sh runs before starting the app.
COMMUNITY = "e2e-community"


@pytest.mark.parametrize("app_path", ["wall", "docs", "forum", "wiki"])
def test_community_apps_have_no_js_errors(
    logged_in: Page, base_url: str, js_errors: JSErrors, app_path: str
) -> None:
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/{app_path}/", wait_until="networkidle"
    )
    js_errors.assert_clean(f"/communities/{COMMUNITY}/{app_path}/")


def test_folder_listing_filters_sorts_and_keeps_its_selection_tools(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The documents listing is the most intricate page in the app.

    Filter and sort are links now, but the selection and the row menus are still
    folder.js, which the branch once had commented out entirely; server-side
    nothing noticed, because the page still rendered.
    """
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )
    rows = logged_in.locator("#objects-table tbody tr")

    # Other tests add to this folder, so what counts is the seeded rows' order.
    def folder_before_document() -> bool:
        text = rows.all_inner_texts()
        titles = [
            row for row in text if "Existing Folder" in row or "E2E Sample" in row
        ]
        return "Existing Folder" in titles[0]

    assert folder_before_document()

    logged_in.get_by_role("link", name="Title").click()
    logged_in.wait_for_url(re.compile(r"[?&]sort=-title"))
    assert not folder_before_document()

    search = logged_in.get_by_role("searchbox")
    search.fill("sample")
    search.press("Enter")
    logged_in.wait_for_url(re.compile(r"[?&]q=sample"))
    assert rows.count() == 1
    assert "E2E Sample" in rows.first.inner_text()
    assert "sort=-title" in logged_in.url, "filtering forgot the sort"

    # The form around the rows still works: picking a row shows its actions.
    rows.first.locator("input[name='object-selected']").check()
    assert logged_in.locator("#horizontal-doc-menu").is_visible()

    js_errors.assert_clean("the folder listing")


def test_a_modal_opens_and_closes(logged_in: Page, base_url: str) -> None:
    """One mechanism: data-modal-open -> showModal(), data-modal-close -> close().

    Closing matters as much as opening. The shim it replaced drove visibility by
    writing `style.display`, which two different CSS files then matched on, and a
    class rule beat the inline style often enough to strand modals open or keep
    them from ever showing.
    """
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )

    trigger = logged_in.locator("[data-modal-open]").first
    assert trigger.count() > 0, "no modal trigger on the folder listing"

    target = trigger.get_attribute("data-modal-open")
    modal = logged_in.locator(target)
    assert not modal.is_visible(), f"{target} was open before anything was clicked"

    trigger.click()
    assert modal.is_visible(), f"clicking the trigger did not open {target}"

    modal.locator("[data-modal-close]").first.click()
    assert not modal.is_visible(), f"{target} stayed open after close"


def test_escape_closes_a_modal(logged_in: Page, base_url: str) -> None:
    """<dialog> gives us ESC for free; the shim's own handler never worked."""
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )

    logged_in.locator('[data-modal-open="#modal-new-folder"]').first.click()
    modal = logged_in.locator("#modal-new-folder")
    assert modal.is_visible()

    logged_in.keyboard.press("Escape")
    assert not modal.is_visible(), "ESC did not close the dialog"


EXISTING_FOLDER = "Existing Folder"


def test_duplicate_folder_name_is_rejected(logged_in: Page, base_url: str) -> None:
    """folder_edit.js checks the title before letting the form submit.

    It had been inert since the Tailwind conversion: it bound to
    `button.btn-primary`, a class the converted modals no longer carry, and
    toggled `hide`, a Bootstrap class that no longer exists.
    """
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )

    logged_in.locator('[data-modal-open="#modal-new-folder"]').first.click()
    modal = logged_in.locator("#modal-new-folder")
    assert modal.is_visible(), "the new-folder modal did not open"

    modal.locator('input[name="title"]').fill(EXISTING_FOLDER)
    modal.locator('button[type="submit"]').click()

    help_text = modal.locator("span.help-block")
    help_text.wait_for(state="visible", timeout=5_000)
    assert EXISTING_FOLDER in help_text.inner_text(), (
        f"expected a duplicate-name error, got {help_text.inner_text()!r}"
    )
    # The modal must still be open: the submit was blocked.
    assert modal.is_visible()


def test_gallery_view_shares_the_folder_behaviour(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The gallery view runs the same module as the table view.

    folder.js and folder_gallery.js were near-duplicates; they are one module now,
    and the gallery has no table to show it broke, so it needs its own exercise.
    """
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )

    logged_in.locator('button[name="view_style"][value="gallery_view"]').first.click()
    logged_in.wait_for_load_state("networkidle")

    js_errors.assert_clean("the gallery view")


def test_document_actions_open_their_modals(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The document page ran a second, forked set of modals.

    Three `_modals_*_alpine.html` templates duplicated the real ones with Alpine
    state, and their triggers used Alpine 2's `$parent`, which Alpine 3 removed:
    the click threw and Move and Replace looked inert. The page is a 200 either
    way, so only a browser sees it.
    """
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle")
    # The listing keeps some of these links in hidden columns, so read the
    # href rather than clicking whichever one comes first.
    href = page.locator('a[href*="/docs/doc/"]').first.get_attribute("href")
    page.goto(f"{base_url}{href}", wait_until="networkidle")

    page.locator("button:has(.fa-ellipsis-h)").first.click()
    page.locator('button[title*="Move"]').first.click()

    js_errors.assert_clean("the document page")
    modal = page.locator("#modal-move-files")
    assert modal.is_visible(), "the Move dialog did not open"

    # folder.js fills the folder listing from a `modal:open` event -- it used to
    # listen for Bootstrap's `show.bs.modal`, which nothing fires any more, so
    # the dialog opened onto an empty table.
    modal.locator(".breadcrumb li").first.wait_for(state="attached", timeout=5_000)
