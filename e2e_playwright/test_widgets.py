# Copyright (c) 2012-2024, Abilian SAS

"""The widget layer: the plugins the pages actually depend on.

test_front_end.py checks that scripts load and pages raise no errors. That is
not the same as the widgets working -- a rich-text field can render as a plain
textarea, and a chart as an empty div, with the console perfectly clean.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

if TYPE_CHECKING:
    from conftest import JSErrors
    from playwright.sync_api import Page

COMMUNITY = "e2e-community"


def test_dashboard_charts_render(logged_in: Page, base_url: str) -> None:
    """uPlot is a Vite entry of its own, loaded by this page and no other.

    The server hands it columnar data in a <script type="application/json">
    block; nothing else on the site uses that path, and a chart that fails to
    draw leaves a perfectly clean console and an empty div.
    """
    logged_in.goto(f"{base_url}/admin/dashboard", wait_until="networkidle")

    for chart_id in ("chart-users", "chart-connections"):
        chart = logged_in.locator(f"#{chart_id}")
        chart.wait_for(state="attached", timeout=15_000)
        # uPlot draws into a <canvas> and builds a legend beside it.
        chart.locator("canvas").wait_for(state="attached", timeout=15_000)
        assert chart.locator(".u-legend .u-series").count() > 0, (
            f"uPlot drew no legend into #{chart_id}"
        )

    # The granularity switch is built from the payload, so its buttons prove
    # the data made it across as well as the library.
    grains = logged_in.locator("#chart-connections .chart-grains button")
    assert grains.count() == 3, "expected daily / weekly / monthly buttons"

    # Switching grain reloads the series: daily covers the same span in many
    # more points than weekly.
    points = "() => document.getElementById('chart-connections').uplot.data[0].length"
    weekly = logged_in.evaluate(points)
    grains.filter(has_text="Daily").click()
    assert logged_in.evaluate(points) > weekly * 5, "the grain switch changed nothing"
    assert grains.filter(has_text="Daily").get_attribute("aria-pressed") == "true"
    assert grains.filter(has_text="Weekly").get_attribute("aria-pressed") == "false"

    canvas = logged_in.locator("#chart-users canvas").first
    assert canvas.bounding_box()["width"] > 100, "the chart canvas has no width"


def test_dashboard_chart_zooms_on_a_drag(logged_in: Page, base_url: str) -> None:
    """Dragging a range zooms the x axis. This is what replaced nvd3's brush.

    nvd3 could not zoom, so it drew a second miniature chart under each plot to
    act as a range selector. uPlot zooms in place -- and if that broke, the
    charts would still render perfectly while eleven years of daily points
    became unreadable with no way in.
    """
    logged_in.goto(f"{base_url}/admin/dashboard", wait_until="networkidle")
    plot = logged_in.locator("#chart-users .u-over")
    plot.wait_for(state="visible", timeout=15_000)
    # Under the overview's first cards: the mouse only reaches what is on screen.
    plot.scroll_into_view_if_needed()

    span = "() => { const s = document.getElementById('chart-users').uplot.scales.x; return s.max - s.min; }"
    before = logged_in.evaluate(span)

    box = plot.bounding_box()
    middle = box["y"] + box["height"] / 2
    logged_in.mouse.move(box["x"] + box["width"] * 0.3, middle)
    logged_in.mouse.down()
    logged_in.mouse.move(box["x"] + box["width"] * 0.7, middle)
    logged_in.mouse.up()

    assert logged_in.evaluate(span) < before / 2, "dragging a range did not zoom"

    logged_in.mouse.dblclick(box["x"] + box["width"] / 2, middle)
    assert logged_in.evaluate(span) == before, "double-click did not reset the zoom"


def test_the_editor_replaces_its_field_only_where_there_is_one(
    logged_in: Page, base_url: str
) -> None:
    """400K of editor, so only the pages with the widget may load it."""
    requested: list[str] = []
    logged_in.on("request", lambda request: requested.append(request.url))

    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/", wait_until="networkidle"
    )
    assert not [url for url in requested if "/editor.js" in url]

    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )
    expect(logged_in.get_by_role("textbox", name="Message")).to_be_visible()
    expect(logged_in.locator("textarea[data-richtext]")).to_be_hidden()
    expect(logged_in.get_by_role("toolbar")).to_be_visible()
    assert [url for url in requested if "/editor.js" in url]


def test_page_scripts_set_up_their_widgets(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """Pages whose own scripts run after the widget layer. Each builds something
    visible, so these fail when such a script stops running, not just on a throw."""
    page = logged_in
    community = f"{base_url}/communities/{COMMUNITY}"

    page.goto(f"{community}/members", wait_until="networkidle")
    expect(page.locator("#user-select")).to_have_attribute("role", "combobox")

    page.goto(f"{community}/docs/", wait_until="networkidle")
    page.goto(f"{page.url.rstrip('/')}/permissions", wait_until="networkidle")
    expect(page.locator("#deactivate_inheritance")).to_be_visible()

    page.goto(f"{base_url}/admin/audit", wait_until="networkidle")
    expect(page.locator("#audit-filters #user-select")).to_have_attribute(
        "role", "combobox"
    )

    page.goto(f"{base_url}/admin/groups", wait_until="networkidle")
    page.get_by_role("link", name="E2E Group").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#user-select")).to_have_attribute("role", "combobox")

    js_errors.assert_clean("pages with their own scripts")


def test_search_endpoints_answer(logged_in: Page, base_url: str) -> None:
    """Both endpoints, over HTTP, from a browser that carries no session.

    They used to 500: `filter_user_communities` read `g.is_manager` bare, and
    that attribute only exists once flask-login has loaded a user. Nothing
    called either endpoint -- typeahead bailed out before making the request
    whenever the index was empty -- so the crash sat there unseen until
    livesearch.js started calling /search/live directly.

    The unit coverage is tests/c_e2e/web/test_search.py; this is the same thing
    through the real stack, with Talisman and the real CSP in front of it.
    """
    # JSONView content-negotiates, so ask for JSON the way livesearch.js does.
    live = logged_in.request.get(
        f"{base_url}/search/live?q=welcome",
        headers={"Accept": "application/json"},
    )
    assert live.ok, f"live search returned HTTP {live.status}"
    assert "results" in live.json()

    page = logged_in.request.get(f"{base_url}/search?q=welcome")
    assert page.ok, f"the search page returned HTTP {page.status}"


def test_file_input_widget_initialises(logged_in: Page, base_url: str) -> None:
    """Every attachment field is one of these; widgets/file.js binds it."""
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )

    if logged_in.locator(".js-file-button").count() == 0:
        pytest.skip("no file input on this form")

    assert logged_in.locator('.js-file-button input[type="file"]').count() > 0


def test_delete_confirmation_opens(logged_in: Page, base_url: str) -> None:
    """folder.js builds a confirmation listing the selected items.

    This threw "$.fn.modal is not defined" until bootbox was replaced: it
    drove Bootstrap's jQuery modal plugin, which went with Bootstrap's JS, so
    every destructive action silently did nothing.
    """
    logged_in.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle"
    )

    checkbox = logged_in.locator('input[name="object-selected"]').first
    if checkbox.count() == 0:
        pytest.skip("nothing in the folder to delete")
    checkbox.check()

    delete_button = logged_in.locator('button[value="delete"]').first
    if delete_button.count() == 0:
        pytest.skip("no delete button on the listing")
    delete_button.click()

    dialog = logged_in.locator("dialog[open]")
    dialog.wait_for(state="visible", timeout=10_000)
    assert dialog.locator("ul.folder-items li").count() > 0, (
        "the confirmation did not list the selected items"
    )


def test_the_audit_log_jumps_to_the_day_picked(logged_in: Page, base_url: str) -> None:
    """A native date input, shown and sent as YYYY-MM-DD whatever the locale.

    Picking a day reloads the log at the entries before that day's end.
    """
    page = logged_in
    page.goto(f"{base_url}/admin/audit", wait_until="networkidle")
    chooser = page.locator("#date-chooser")
    # The seed ran today, so the newest entries are today's.
    today = chooser.input_value()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", today), today

    todays_heading = page.locator(f'h2 time[datetime="{today}"]')

    chooser.fill("2000-01-01")
    page.wait_for_url(re.compile(r"before=2000-01-0[12]T"))
    expect(todays_heading).to_have_count(0)

    page.locator("#date-chooser").fill(today)
    page.wait_for_url(re.compile(r"before=(?!2000-)"))
    expect(todays_heading).to_be_visible()


#: What the server answers as one types, for a test that needs no index.
SUGGESTIONS = """
<div class="ads-combobox__list sbe-suggest__panel" id="suggestions" role="listbox">
  <a class="ads-combobox__option sbe-suggest__option" role="option" id="s-1"
     href="/communities/e2e-community/forum/" aria-selected="false">First</a>
  <a class="ads-combobox__option sbe-suggest__option" role="option" id="s-2"
     href="/communities/" aria-selected="false">Second</a>
</div>"""


def test_the_bar_suggests_as_one_types(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """`/` reaches the field from the page, which opens on what is recent; typing
    asks the server, the arrows move, Escape closes, Enter opens."""
    page = logged_in
    page.route(
        "**/search/suggest?*",
        lambda route: route.fulfill(
            status=200, body=SUGGESTIONS, content_type="text/html"
        ),
    )
    page.goto(f"{base_url}/", wait_until="networkidle")
    field = page.locator('.sbe-suggest input[name="q"]')

    page.keyboard.press("/")
    expect(field).to_be_focused()
    # On an empty field: what one searched and opened lately.
    expect(page.locator("#suggestions")).to_be_visible()
    field.press_sequentially("we")
    expect(page.locator("#suggestions")).to_be_visible()
    expect(field).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#s-1")).to_have_attribute("aria-selected", "true")

    field.press("ArrowDown")
    expect(page.locator("#s-2")).to_have_attribute("aria-selected", "true")
    expect(field).to_have_attribute("aria-activedescendant", "s-2")

    field.press("Escape")
    expect(page.locator("#suggestions")).to_have_count(0)
    expect(field).to_have_value("we")

    field.press_sequentially("l")
    expect(page.locator("#s-1")).to_have_attribute("aria-selected", "true")
    with page.expect_navigation():
        field.press("Enter")
    assert page.url.endswith("/communities/e2e-community/forum/"), page.url

    js_errors.assert_clean("the bar's suggestions")


def test_selecting_all_members_shows_what_applies_to_them(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/members", wait_until="networkidle")
    boxes = page.locator('input[name="selected"]')
    bar = page.locator("#members-selection")
    expect(bar).to_be_hidden()

    page.locator("[data-select-all]").check()

    expect(bar).to_be_visible()
    for box in boxes.all():
        expect(box).to_be_checked()
    js_errors.assert_clean("the members' selection")
