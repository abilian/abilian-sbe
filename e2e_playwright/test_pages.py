# Copyright (c) 2012-2024, Abilian SAS

"""Smaller behaviours: the group pages, audit filters, native selects, the forum."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from playwright.sync_api import expect
from test_members import _pick

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import JSErrors
    from playwright.sync_api import Page, Route

COMMUNITY = "e2e-community"


def _admin_group(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/groups", wait_until="networkidle")
    page.get_by_role("link", name="E2E Group").click()
    page.wait_for_load_state("networkidle")


def test_admin_group_picker_adds_a_member(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _admin_group(page, base_url)

    _pick(page, "#user-select", "Gus", "gus.grouped@example.com")
    page.locator('#add-user-role button[type="submit"]').click()
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("gus.grouped@example.com").first).to_be_visible()
    js_errors.assert_clean("adding to a group in the admin")


def test_group_form_saves_several_roles_from_a_native_select(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    _admin_group(page, base_url)
    page.get_by_role("link", name="Edit").click()
    page.wait_for_load_state("networkidle")

    roles = page.locator('select[name="roles"]')
    expect(roles).to_have_attribute("multiple", "")
    values = roles.locator("option").evaluate_all("nodes => nodes.map(n => n.value)")
    roles.select_option(values[:2])
    page.get_by_role("button", name="Save").click()
    page.wait_for_load_state("networkidle")

    page.get_by_role("link", name="Edit").click()
    page.wait_for_load_state("networkidle")
    assert sorted(
        page.locator('select[name="roles"]').evaluate(
            "s => [...s.selectedOptions].map(o => o.value)"
        )
    ) == sorted(values[:2])

    js_errors.assert_clean("saving a group's roles")


def test_admin_users_shows_the_email_under_the_name_and_filters_on_it(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(f"{base_url}/admin/users", wait_until="networkidle")

    row = page.locator("#users-table tbody tr", has_text="Paula Picker")
    expect(row.locator("td").nth(1)).to_contain_text("paula.picker@example.com")

    page.fill('main input[type="search"]', "paula.picker")
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle")
    expect(page.locator("#users-table tbody tr")).to_have_count(1)
    expect(row).to_be_visible()

    js_errors.assert_clean("the users table")


def test_user_form_saves_groups_from_a_native_select(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The groups come from a query and the labels are model objects', unlike the
    roles above. A blank row would be a choice in its own right in a native list,
    so there must not be one."""
    page = logged_in
    page.goto(f"{base_url}/admin/users", wait_until="networkidle")
    page.locator("table a", has_text="Rolf Roleholder").first.click()
    page.wait_for_load_state("networkidle")
    edit_url = page.url

    groups = page.locator('select[name="groups"]')
    expect(groups).to_have_attribute("multiple", "")
    assert groups.locator("option").all_text_contents() == ["E2E Group"]
    groups.select_option(label="E2E Group")
    page.get_by_role("button", name="Save").click()
    page.wait_for_load_state("networkidle")

    page.goto(edit_url, wait_until="networkidle")
    selected = page.locator('select[name="groups"]').evaluate(
        "s => [...s.selectedOptions].map(o => o.textContent.trim())"
    )
    assert selected == ["E2E Group"]
    js_errors.assert_clean("saving a user's groups")


def test_social_group_pickers(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The admin picker offers members only, so the member goes first."""
    page = logged_in
    page.goto(f"{base_url}/social/groups", wait_until="networkidle")
    page.get_by_role("link", name="E2E Group").first.click()
    page.wait_for_load_state("networkidle")

    _pick(page, "#user-select", "Greta", "greta.groupadmin@example.com")
    page.locator('button[name="action"][value="add"]').click()
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link", name="Greta Groupadmin").first).to_be_visible()

    _pick(page, "#admin-select", "Greta", "Greta")
    page.locator('button[name="action"][value="add-admin"]').click()
    page.wait_for_load_state("networkidle")

    js_errors.assert_clean("the social group page")


def test_audit_filters_submit_themselves(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(f"{base_url}/admin/audit", wait_until="networkidle")

    with page.expect_navigation():
        page.locator("#audit-filters #user-select").fill("Eva")
        page.locator("#user-select-results [role=option]").first.click()
    assert re.search(r"user=\d+", page.url), page.url
    # The choice survives the reload, by name.
    expect(page.locator("#user-select")).to_have_value(re.compile("Eva"))

    with page.expect_navigation():
        page.locator("#user-select").fill("")
        page.locator("#user-select").blur()
    assert "user=&" in page.url or page.url.endswith("user="), page.url

    with page.expect_navigation():
        page.fill("#date-chooser", "2026-01-15")
        page.locator("#date-chooser").dispatch_event("change")
    assert "before=2026-01-1" in page.url, page.url

    types = page.locator('select[name="types"]')
    if types.locator("option").count() > 1:
        with page.expect_navigation():
            types.select_option(index=1)

    js_errors.assert_clean("the audit filters")


def test_community_home_sort_submits_itself(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(f"{base_url}/communities/", wait_until="networkidle")
    with page.expect_navigation():
        page.locator('select[name="sort"]').select_option("activity")
    assert "sort=activity" in page.url
    js_errors.assert_clean("sorting communities")


def test_a_reply_is_written_in_the_editor_and_posted(
    logged_in: Page, base_url: str, js_errors: JSErrors, tmp_path: Path
) -> None:
    """The thread's page is on the design system; its reply form keeps the app's
    editor and uploader, loaded without Tailwind, under the Content Security
    Policy."""
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/forum/", wait_until="networkidle")
    page.get_by_role("link", name="Welcome to the new members").first.click()
    page.wait_for_load_state("networkidle")

    editor = page.locator("#reply .richtext-content .ProseMirror")
    editor.click()
    page.locator('#reply [data-command="toggleBold"]').click()
    editor.press_sequentially("A bold reply")
    note = tmp_path / "minutes.txt"
    note.write_text("Minutes.")
    page.set_input_files("#reply .js-file-button input", note)
    # Uploaded straight away: its handle goes with the form.
    expect(page.locator("#reply .selected-files input[type=hidden]")).to_have_count(1)
    page.get_by_role("button", name="Send").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator('[id^="post_"] .ads-prose strong').last).to_have_text(
        "A bold reply"
    )
    expect(page.locator(".ads-file__name", has_text="minutes.txt")).to_be_visible()
    js_errors.assert_clean("replying in a thread")


def test_forum_filters_narrow_the_list(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The period as a pill, and the filter on titles, which the server applies."""
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/forum/", wait_until="networkidle")

    page.get_by_role("link", name="Most read this week").click()
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("/forum/week"), page.url

    page.goto(f"{base_url}/communities/{COMMUNITY}/forum/", wait_until="networkidle")
    search = page.get_by_role("searchbox", name="Filter discussions by title")
    search.fill("welcome")
    search.press("Enter")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link", name="Welcome to the new members")).to_be_visible()

    search = page.get_by_role("searchbox", name="Filter discussions by title")
    search.fill("no such words")
    search.press("Enter")
    page.wait_for_load_state("networkidle")
    expect(
        page.get_by_text("No discussion has these words in its title.")
    ).to_be_visible()

    js_errors.assert_clean("the forum's filters")


def test_new_thread_counts_its_title(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )

    counter = page.locator(".thread-title-counter")
    expect(counter).to_have_text("0/150")
    page.fill("#title", "Hello")
    expect(counter).to_have_text("5/150")

    js_errors.assert_clean("the new thread form")


def test_community_settings_save_their_native_selects(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    settings = f"{base_url}/communities/{COMMUNITY}/settings"
    page.goto(settings, wait_until="networkidle")

    page.fill('textarea[name="description"]', "Described in a browser test.")
    kind = page.locator('select[name="type"]')
    kind.select_option(label="participative")
    wanted = kind.input_value()
    page.locator(
        '#edit-form button[type="submit"], button[name="__action"]'
    ).first.click()
    page.wait_for_load_state("networkidle")

    page.goto(settings, wait_until="networkidle")
    expect(page.locator('select[name="type"]')).to_have_value(wanted)
    js_errors.assert_clean("the community settings")


def test_wiki_attachment_is_deleted_after_asking_by_name(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    wiki = f"{base_url}/communities/{COMMUNITY}/wiki"
    page.goto(f"{wiki}/new", wait_until="networkidle")
    page.fill('#edit-form input[name="title"]', "Page with an attachment")
    page.fill('#edit-form textarea[name="body_src"]', "Body.")
    page.locator('#edit-form button[value="create"]').click()
    page.wait_for_load_state("networkidle")

    page.locator('[data-modal-open="#upload-files"]').first.click()
    name = "notes.txt"
    page.locator('#upload-files input[name="attachments"]').set_input_files(
        {"name": name, "mimeType": "text/plain", "buffer": b"hello"}
    )
    page.locator('#upload-files button[value="upload"]').click()
    page.wait_for_load_state("networkidle")
    page.goto(f"{wiki}/page/?title=Page+with+an+attachment", wait_until="networkidle")

    row = page.locator("#attachments li", has_text=name)
    row.locator('button[value="delete"]').click()
    dialog = page.locator("dialog[open]")
    expect(dialog.locator("h2")).to_have_text(f'"{name}"')
    dialog.get_by_role("button", name="Delete").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator("#attachments li", has_text=name)).to_have_count(0)
    js_errors.assert_clean("deleting a wiki attachment")


def test_pdf_viewer_renders_the_document(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """PDF.js has to have actually drawn the page: a clean console proves
    nothing if the viewer never started. The page runs under the Content
    Security Policy, so a worker, decoder or font it refuses fails the test."""
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle")
    row = page.locator("#objects-table tbody tr", has_text="E2E Sample")
    selected = row.locator('input[name="object-selected"]').get_attribute("value")
    doc_id = selected.rsplit(":", 1)[1]

    def serve_pdf(route: Route) -> None:
        route.fulfill(content_type="application/pdf", body=_text_pdf("Hello PDF"))

    page.route(re.compile(rf"/doc/{doc_id}/download"), serve_pdf)
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/docs/doc/{doc_id}/view_pdf",
        wait_until="networkidle",
    )

    expect(page.locator("#pdf-viewer")).to_have_attribute("data-pages", "1")
    expect(page.locator(".pdfViewer .page canvas")).to_have_count(1)
    expect(page.locator("[data-page-count]")).to_have_text("1")
    # Helvetica is not embedded: drawing it takes PDF.js's standard fonts.
    expect(page.locator(".pdfViewer .textLayer")).to_contain_text("Hello PDF")
    js_errors.assert_clean("the PDF viewer")


def _text_pdf(text: str) -> bytes:
    """A one-page PDF saying `text` in Helvetica, which it does not embed."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    pdf += b"startxref\n%d\n%%%%EOF\n" % xref
    return pdf


def test_json_view_highlights_its_output(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """Its one line of setup moved to a file, on a page outside the base template."""
    page = logged_in
    page.goto(f"{base_url}/search/live?q=e2e", wait_until="networkidle")
    expect(page.locator("code.hljs")).to_be_visible()
    js_errors.assert_clean("the JSON view")


def test_dynamic_rows_add_and_remove(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """No page in this application has a repeated field yet, so one is injected."""
    page = logged_in
    table = """
      <table id="phones" class="js-widget" data-init-with="dynamicRowWidget"
             data-prefix="phones">
        <thead><tr><th>Number</th></tr></thead>
        <tbody><tr><td>
          <input id="phones-0-number" name="phones-0-number" value="555"
                 data-short-name="number">
          <select id="phones-0-kind" name="phones-0-kind"><option>home</option></select>
        </td></tr></tbody>
      </table>"""

    def inject(route: Route) -> None:
        response = route.fetch()
        route.fulfill(
            response=response,
            body=response.text().replace("</body>", f"{table}</body>"),
        )

    page.route(f"{base_url}/communities/", inject)
    page.goto(f"{base_url}/communities/", wait_until="networkidle")

    rows = page.locator("#phones tbody tr")
    page.locator('#phones thead button[aria-label="Add"]').click()
    expect(rows).to_have_count(2)

    added = rows.nth(1)
    expect(added.locator("input")).to_have_attribute("name", "phones-1-number")
    expect(added.locator("input")).to_have_value("")
    expect(added.locator("select")).to_have_attribute("name", "phones-1-kind")

    rows.first.locator('button[aria-label="Remove"]').click()
    expect(rows).to_have_count(1)
    expect(rows.first.locator("input")).to_have_attribute("name", "phones-1-number")

    js_errors.assert_clean("the repeated field")


def test_community_delete_asks_first_then_posts(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The one Alpine expression that calls a method, on a form found by x-ref."""
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/settings", wait_until="networkidle")

    destroy = page.locator("button", has_text="Destroy community")
    confirm = page.get_by_role("button", name="Destroy", exact=True)
    destroy.click()
    expect(confirm).to_be_visible()
    page.get_by_role("button", name="Cancel").last.click()
    expect(confirm).to_be_hidden()

    # The community stays: the suite needs it, so the post goes no further.
    action = page.locator('form[x-ref="deleteForm"]').get_attribute("action")
    page.route(
        f"{base_url}{action}",
        lambda route: route.fulfill(status=200, body="stopped by the test"),
    )
    destroy.click()
    with page.expect_request(f"{base_url}{action}") as posted:
        confirm.click()
    assert posted.value.method == "POST"

    js_errors.assert_clean("the community delete dialog")


def test_a_flash_message_can_be_dismissed(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    page = logged_in
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/members/wizard/step1",
        wait_until="networkidle",
    )
    page.get_by_role("button", name="Next step").click()
    page.wait_for_load_state("networkidle")

    message = page.locator('[role="alert"]', has_text="No new members were found")
    expect(message).to_be_visible()
    message.get_by_role("button", name="Dismiss").click()
    expect(message).to_be_hidden()

    js_errors.assert_clean("dismissing a message")


def test_a_document_takes_the_whole_width_and_gives_it_back(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The button is a checkbox in a label; the column goes by a CSS `:has()`."""
    page = logged_in
    page.goto(f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle")
    page.locator("#objects-table tbody a", has_text="E2E Sample").first.click()
    page.wait_for_load_state("networkidle")
    details = page.locator("#doc-details")
    expect(details).to_be_visible()

    page.locator("label", has_text="Full width").click()
    expect(details).to_be_hidden()
    page.locator("label", has_text="Details").click()
    expect(details).to_be_visible()

    js_errors.assert_clean("the document's width")


def test_form_tabs_switch(logged_in: Page, base_url: str, js_errors: JSErrors) -> None:
    """Tabs in widgets/render_for_edit.html. No form here declares groups yet, so
    its markup is injected: Alpine picks it up like any other."""
    page = logged_in
    panel = """
      <div id="tabs" x-data="{ activeTab: 'first-tab' }">
        <button type="button" id="second" @click="activeTab = 'second-tab'"
                :class="activeTab === 'second-tab' ? 'on' : 'off'">Second</button>
        <div id="first-panel" x-show="activeTab === 'first-tab'">One</div>
        <div id="second-panel" x-show="activeTab === 'second-tab'">Two</div>
      </div>"""

    def inject(route: Route) -> None:
        response = route.fetch()
        route.fulfill(
            response=response,
            body=response.text().replace("</body>", f"{panel}</body>"),
        )

    page.route(f"{base_url}/communities/", inject)
    page.goto(f"{base_url}/communities/", wait_until="networkidle")

    expect(page.locator("#first-panel")).to_be_visible()
    expect(page.locator("#second-panel")).to_be_hidden()
    page.locator("#second").click()
    expect(page.locator("#second")).to_have_class("on")
    expect(page.locator("#first-panel")).to_be_hidden()
    expect(page.locator("#second-panel")).to_be_visible()

    js_errors.assert_clean("form tabs")


def test_no_inline_script_runs_or_is_refused(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The policy actually forbids inline scripts, and pages live with that."""
    page = logged_in
    response = page.goto(f"{base_url}/communities/", wait_until="networkidle")
    policy = response.headers["content-security-policy"]
    script_src = next(d for d in policy.split(";") if "script-src" in d)
    assert "'unsafe-inline'" not in script_src, policy
    assert "'unsafe-eval'" not in script_src, policy

    for path in (
        f"/communities/{COMMUNITY}/docs/",
        f"/communities/{COMMUNITY}/members",
        f"/communities/{COMMUNITY}/members/wizard/step1",
        f"/communities/{COMMUNITY}/wiki/",
        f"/communities/{COMMUNITY}/forum/",
        "/admin/audit",
        "/admin/dashboard",
        "/preferences/",
        # Mon fil, on the Abilian Design System, whose shell has no inline script.
        "/",
    ):
        page.goto(f"{base_url}{path}", wait_until="networkidle")
    js_errors.assert_clean("pages under the policy")


def test_a_folded_sidebar_remembered_leaves_the_bar_alone(
    logged_in: Page, base_url: str
) -> None:
    """Folding is a sidebar's, remembered per origin: another ADS application on the
    same host can leave it set. Applied to the horizontal bar, it squeezed the bar
    into a rail's width and the search lay over the navigation."""
    page = logged_in
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.evaluate("localStorage.setItem('ads-sidebar-folded', '1')")
    page.reload(wait_until="networkidle")

    expect(page.locator(".ads-app")).not_to_have_class(re.compile("ads-app--folded"))
    nav = page.locator(".sbe-primary").bounding_box()
    search = page.locator(".sbe-search").bounding_box()
    assert nav
    assert search
    assert nav["x"] + nav["width"] <= search["x"], (nav, search)
