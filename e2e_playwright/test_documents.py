# Copyright (c) 2012-2024, Abilian SAS

"""The actions on a folder's rows, its dialogs, comments on a document, and the
permissions page."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from zipfile import ZipFile

from playwright.sync_api import expect
from test_members import _pick

if TYPE_CHECKING:
    from conftest import JSErrors
    from playwright.sync_api import Locator, Page

COMMUNITY = "e2e-community"


def _open_folder(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle")


def _row_menu(page: Page, title: str) -> Locator:
    """The row of `title`, with its action menu open."""
    row = page.locator("#objects-table tbody tr", has_text=title)
    row.locator("td").last.locator("summary").click()
    return row


def _new_folder(page: Page, title: str) -> None:
    page.locator('[data-modal-open="#modal-new-folder"]').first.click()
    dialog = page.locator("#modal-new-folder")
    dialog.locator('input[name="title"]').fill(title)
    dialog.locator('button[type="submit"]').click()
    expect(page.locator("#objects-table tbody tr", has_text=title)).to_be_visible()


def test_new_folder_title_is_checked_and_enter_does_not_submit(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _open_folder(page, base_url)

    page.locator('[data-modal-open="#modal-new-folder"]').first.click()
    dialog = page.locator("#modal-new-folder")
    title = dialog.locator('input[name="title"]')
    title.fill("Existing Folder")

    title.press("Enter")
    expect(dialog).to_be_visible()

    dialog.locator('button[type="submit"]').click()
    expect(dialog.locator(".help-block")).to_be_visible()

    js_errors.assert_clean("the new folder dialog")


def test_a_title_with_markup_stays_text_through_move_and_delete(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """Titles are user input. These dialogs built HTML from them."""
    page = logged_in
    title = "<b>Bold</b> folder"
    _open_folder(page, base_url)
    _new_folder(page, title)

    # Delete asks about this folder by name, written as text.
    _row_menu(page, title).get_by_role("button", name="Delete").click()
    confirm = page.locator("dialog[open]")
    expect(confirm.locator("ul.folder-items li")).to_have_text([title])
    assert confirm.locator("ul.folder-items b").count() == 0
    confirm.get_by_role("button", name="Cancel").click()

    # Move it into the seeded folder. The move dialog lists folders by title, so
    # it is opened from inside, where its own name appears in the breadcrumbs.
    _row_menu(page, title).get_by_role("button", name="Move").click()
    move = page.locator("#modal-move-files")
    expect(move).to_be_visible()
    move.locator("tbody a", has_text="Existing Folder").click()
    expect(move.locator(".breadcrumb")).to_contain_text("Existing Folder")
    submit = page.locator("#modal-move-button-submit")
    expect(submit).to_be_enabled()
    submit.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#objects-table tbody tr", has_text=title)).to_have_count(0)

    # And it arrived.
    page.locator("#objects-table tbody a", has_text="Existing Folder").first.click()
    page.wait_for_load_state("networkidle")
    row = page.locator("#objects-table tbody tr", has_text=title)
    expect(row).to_be_visible()

    # Delete for real. A subfolder's own Delete used to post to the subfolder
    # with nothing selected, and deleted nothing.
    _row_menu(page, title).get_by_role("button", name="Delete").click()
    page.locator("dialog[open]").get_by_role("button", name="Delete").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#objects-table tbody tr", has_text=title)).to_have_count(0)

    js_errors.assert_clean("moving and deleting a folder")


def test_edit_document_dialog_is_filled_from_its_row(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _open_folder(page, base_url)

    _row_menu(page, "E2E Sample").get_by_role("button", name="Edit").click()
    dialog = page.locator("#modal-edit")
    expect(dialog).to_be_visible()
    expect(dialog.locator('input[name="title"]')).to_have_value("E2E Sample.png")
    assert "/doc/" in (page.locator("#modal-edit-form").get_attribute("action") or "")
    dialog.get_by_role("button", name="Cancel").click()

    js_errors.assert_clean("the edit dialog")


def test_selection_shows_and_hides_the_actions(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _open_folder(page, base_url)
    menu = page.locator(".ads-bulkbar")
    rows = page.locator('input[name="object-selected"]')

    page.locator(".doc-check-all").check()
    assert all(rows.nth(i).is_checked() for i in range(rows.count()))
    expect(menu).to_be_visible()

    page.locator(".doc-check-all").uncheck()
    assert not any(rows.nth(i).is_checked() for i in range(rows.count()))
    expect(menu).to_be_hidden()

    js_errors.assert_clean("selecting rows")


def test_the_download_button_zips_the_selection(logged_in: Page, base_url: str) -> None:
    """Not `js_errors`: a navigation that becomes a download reads as aborted."""
    page = logged_in
    _open_folder(page, base_url)

    page.locator(".doc-check-all").check()
    with page.expect_download() as download:
        page.locator('.ads-bulkbar button[value="download"]').click()

    with ZipFile(download.value.path()) as archive:
        assert "E2E Sample.png" in archive.namelist()


def test_change_owner_posts_the_person_picked(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _open_folder(page, base_url)

    row = page.locator("#objects-table tbody tr", has_text="E2E Sample")
    owner = row.locator(".sbe-person")
    previous_owner = owner.get_attribute("title")
    row.locator('input[name="object-selected"]').check()
    page.locator('[data-modal-open="#modal-change-owner"]').click()
    dialog = page.locator("#modal-change-owner")
    expect(dialog).to_be_visible()
    assert dialog.locator('.selected-items input[name="object-selected"]').count() == 1

    # Inside the dialog's box, and not clipped by it.
    _pick(page, "#new_owner", "Paula", "paula.picker@example.com")
    dialog.get_by_role("button", name="Change owner").click()
    page.wait_for_load_state("networkidle")

    assert owner.get_attribute("title") != previous_owner
    js_errors.assert_clean("changing the owner")


def test_the_gallery_selects_and_acts_like_the_table(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The tiles are the same form as the rows: ticking one shows what applies to
    the selection, and its menu fills the same dialogs."""
    page = logged_in
    _open_folder(page, base_url)
    page.locator('button[name="view_style"][value="gallery_view"]').first.click()
    page.wait_for_load_state("networkidle")

    tile = page.locator(".sbe-gallery__item", has_text="E2E Sample")
    expect(page.locator(".ads-bulkbar")).to_be_hidden()
    tile.locator('input[name="object-selected"]').check()
    expect(page.locator(".ads-bulkbar")).to_be_visible()

    tile.locator("summary").click()
    tile.get_by_role("button", name="Edit").click()
    expect(page.locator("#modal-edit input[name='title']")).to_have_value(
        "E2E Sample.png"
    )
    page.locator("#modal-edit").get_by_role("button", name="Cancel").click()

    # While something is ticked, the selection's bar takes the view switch's place.
    tile.locator('input[name="object-selected"]').uncheck()
    page.locator('button[name="view_style"][value="thumbnail_view"]').first.click()
    page.wait_for_load_state("networkidle")
    js_errors.assert_clean("the gallery")


def test_a_comment_is_posted_edited_and_deleted(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """On the document's page; each of the comment's dialogs is its own, filled by
    the server."""
    page = logged_in
    _open_folder(page, base_url)
    page.locator("#objects-table tbody a", has_text="E2E Sample").first.click()
    comments = page.locator("section", has=page.locator("#comments"))

    comments.get_by_label("Your comment on the document").fill("Looks good.")
    comments.get_by_role("button", name="Post the comment").click()
    comment = comments.locator("li", has_text="Looks good.")
    expect(comment).to_be_visible()

    comment.get_by_label("Actions on the comment").click()
    comment.get_by_role("button", name="Edit").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_role("textbox").fill("Looks good to me.")
    dialog.get_by_role("button", name="Save changes").click()
    comment = comments.locator("li", has_text="Looks good to me.")
    expect(comment).to_be_visible()

    comment.get_by_label("Actions on the comment").click()
    comment.get_by_role("button", name="Delete").click()
    page.locator("dialog[open]").get_by_role("button", name="Delete").click()
    expect(comments.locator("li", has_text="Looks good")).to_have_count(0)

    js_errors.assert_clean("commenting on a document")


def test_permissions_page(logged_in: Page, base_url: str, js_errors: JSErrors) -> None:
    page = logged_in
    _open_folder(page, base_url)
    page.goto(f"{page.url.rstrip('/')}/permissions", wait_until="networkidle")

    # Inheritance is a plain form now: off, and back on.
    page.locator("#deactivate_inheritance").click()
    page.wait_for_load_state("networkidle")
    page.locator("#activate_inheritance").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#deactivate_inheritance")).to_be_visible()

    page.locator('[data-modal-open="#modal-add-user-local-role"]').click()
    dialog = page.locator("#modal-add-user-local-role")
    expect(dialog).to_be_visible()
    _pick(page, "#user-select", "Rolf", "rolf.roleholder@example.com")
    dialog.locator("#role-select").select_option("writer")
    dialog.get_by_role("button", name="Give the role").click()
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("link", name="Rolf Roleholder").first).to_be_visible()
    js_errors.assert_clean("the permissions page")
    expect(page).to_have_url(re.compile(r"/permissions"))
