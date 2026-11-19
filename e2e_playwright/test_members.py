# Copyright (c) 2012-2024, Abilian SAS

"""Adding people: the members wizard, and the user pickers.

Each test ends by looking at what the server did. The wizard once looked fine and
went nowhere: its Next button submitted a form whose class had been renamed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import JSErrors
    from playwright.sync_api import Page

COMMUNITY = "e2e-community"


def _step1(page: Page, base_url: str) -> None:
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/members/wizard/step1",
        wait_until="networkidle",
    )


def _member_row(page: Page, email: str):
    return page.locator("#members-table tbody tr", has_text=email)


def test_wizard_adds_existing_and_new_people_from_pasted_addresses(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _step1(page, base_url)

    page.fill(
        "#wizard-emails",
        "eva.existing@example.com, nina.new@example.com\nnot-an-address",
    )
    # What will happen to each shows as it is typed; one role for all.
    expect(page.locator("[data-invitees]")).to_contain_text("not-an-address")
    page.select_option("#invite-role", "manager")
    page.get_by_role("button", name="Next step").click()
    page.wait_for_load_state("networkidle")

    # Typed addresses go straight on to the accounts to make.
    # A name is required before the account can be created.
    page.locator("[data-wizard-save]").click()
    expect(page.locator(".wizard-warning")).to_be_visible()

    page.fill('input[name="first_name"]', "Nina")
    page.fill('input[name="last_name"]', "New")
    page.locator("[data-wizard-save]").click()
    page.wait_for_url(re.compile(r"/members"))

    eva = _member_row(page, "eva.existing@example.com")
    expect(eva.locator('select[name="role"]')).to_have_value("manager")
    expect(_member_row(page, "nina.new@example.com")).to_be_visible()

    js_errors.assert_clean("the members wizard")


def test_wizard_can_drop_someone_at_each_step(
    logged_in: Page, base_url: str, js_errors: JSErrors, tmp_path: Path
) -> None:
    """From a spreadsheet, which has a step to review the accounts that exist."""
    page = logged_in
    _step1(page, base_url)

    csv = tmp_path / "members.csv"
    csv.write_text(
        "rita.removed@example.com;Rita;Removed;member\n"
        "otto.other@example.com;Otto;Other;member\n"
        "oskar.other@example.com;Oskar;Other;member\n"
    )
    page.set_input_files("#csv_file", csv)
    page.get_by_role("button", name="Next step").click()
    page.wait_for_load_state("networkidle")

    page.locator('[data-wizard-remove="rita.removed@example.com"]').click()
    expect(page.get_by_text("There is no existing accounts")).to_be_visible()

    page.get_by_role("button", name="Next step").click()
    page.wait_for_load_state("networkidle")

    row = page.locator("tr[data-wizard-row]", has_text="otto.other@example.com")
    row.locator("[data-wizard-remove]").click()
    expect(row).to_have_count(0)

    page.locator("[data-wizard-save]").click()
    page.wait_for_url(re.compile(r"/members"))

    expect(_member_row(page, "oskar.other@example.com")).to_be_visible()
    expect(_member_row(page, "rita.removed@example.com")).to_have_count(0)
    expect(_member_row(page, "otto.other@example.com")).to_have_count(0)

    js_errors.assert_clean("dropping people in the wizard")


def test_wizard_takes_a_csv_file(
    logged_in: Page, base_url: str, js_errors: JSErrors, tmp_path: Path
) -> None:
    page = logged_in
    _step1(page, base_url)

    csv = tmp_path / "members.csv"
    csv.write_text("carla.csv@example.com;Carla;Csv;manager\n")
    page.set_input_files("#csv_file", csv)
    page.get_by_role("button", name="Next step").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(re.compile(r"/wizard/step2$"))
    page.get_by_role("button", name="Next step").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator('input[name="first_name"]')).to_have_value("Carla")
    expect(page.locator('select[name="role"]')).to_have_value("manager")

    page.locator("[data-wizard-save]").click()
    page.wait_for_url(re.compile(r"/members"))

    carla = _member_row(page, "carla.csv@example.com")
    expect(carla.locator('select[name="role"]')).to_have_value("manager")

    js_errors.assert_clean("a CSV import")


def test_wizard_says_so_when_given_nothing(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _step1(page, base_url)

    page.get_by_role("button", name="Next step").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(re.compile(r"/wizard/step1$"))
    expect(page.get_by_text("No new members were found")).to_be_visible()

    js_errors.assert_clean("an empty wizard")


def _pick(page: Page, box_selector: str, typed: str, shown: str) -> None:
    """Type into a picker and click the suggestion that contains `shown`."""
    box = page.locator(box_selector)
    box.fill(typed)
    option = page.locator(
        f"#{box.get_attribute('id')}-results [role=option]", has_text=shown
    )
    option.click()


def test_picker_adds_a_member(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/members", wait_until="networkidle")

    _pick(page, "#user-select", "Paula", "paula.picker@example.com")
    expect(page.locator("#user-select")).to_have_value(re.compile("Paula Picker"))
    page.get_by_role("button", name="Add", exact=True).click()
    page.wait_for_load_state("networkidle")

    expect(_member_row(page, "paula.picker@example.com")).to_be_visible()
    js_errors.assert_clean("picking a member")


@pytest.mark.parametrize(
    "answer",
    [{"json": {"results": 5}}, {"status": 500, "body": "boom"}],
    ids=["a bug drawing the suggestions", "a failed search"],
)
def test_a_failure_is_reported_rather_than_taken_for_no_suggestions(
    answer: dict, logged_in: Page, base_url: str
) -> None:
    """Sentry only hears about what is left uncaught."""
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/members", wait_until="networkidle")
    page.route("**/users/json*", lambda route: route.fulfill(**answer))

    with page.expect_event("pageerror"):
        page.locator("#user-select").fill("Paula")

    expect(page.locator("#user-select-results")).to_be_hidden()


def test_picker_keyboard_and_abandoned_text(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """Arrow keys and Enter choose. Text never turned into a choice does not stay."""
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/members", wait_until="networkidle")
    box = page.locator("#user-select")
    hidden = page.locator('#add-user-role input[type="hidden"][name="user"]')

    box.fill("nobody-by-that-name")
    box.blur()
    expect(box).to_have_value("")

    box.fill("Paula")
    expect(page.locator("#user-select-results [role=option]").first).to_be_visible()
    box.press("ArrowDown")
    box.press("Enter")

    expect(box).to_have_value(re.compile("Paula Picker"))
    assert hidden.input_value().isdigit()
    expect(page).to_have_url(re.compile(r"/members$"))

    js_errors.assert_clean("the picker's keyboard")


def test_role_select_saves_itself(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/members", wait_until="networkidle")

    role = page.locator("#members-table tbody tr").first.locator('select[name="role"]')
    wanted = "member" if role.input_value() == "manager" else "manager"
    with page.expect_navigation():
        role.select_option(wanted)

    expect(
        page.locator("#members-table tbody tr").first.locator('select[name="role"]')
    ).to_have_value(wanted)
    role = page.locator("#members-table tbody tr").first.locator('select[name="role"]')
    with page.expect_navigation():
        role.select_option("manager" if wanted == "member" else "member")

    js_errors.assert_clean("changing a role")
