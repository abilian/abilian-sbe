# Copyright (c) 2012-2024, Abilian SAS

"""Forms submitted through the browser, end to end.

The rest of the suite checks that the editor and the upload widget initialise.
These fill them in and submit, and check what the server kept, since a widget
that initialises can still lose what was typed into it.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import ZipFile

from PIL import Image
from playwright.sync_api import expect

if TYPE_CHECKING:
    from conftest import JSErrors
    from playwright.sync_api import Dialog, Locator, Page, Route

#: Seeded by seed.py, which serve.sh runs before starting the app.
COMMUNITY = "e2e-community"

ATTACHMENT_NAME = "e2e-attachment.txt"
ATTACHMENT_BODY = b"attached through the browser"
UPLOAD_URL = re.compile(r"/upload/(\?|$)")
EDITOR = ".richtext-content .ProseMirror"
#: A post's text on a thread's page.
POST_BODY = '[id^="post_"] .ads-prose'


def test_a_thread_with_an_attachment(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The message goes through the editor, the file through the upload widget
    (posted to the uploads endpoint, then a hidden handle on submit)."""
    page = logged_in
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )

    page.fill("#title", "A thread with an attachment")
    editor = page.locator(EDITOR)
    editor.click()
    editor.press_sequentially("Typed into the rich text editor.")

    page.locator('.js-file-button input[type="file"]').set_input_files(
        {
            "name": ATTACHMENT_NAME,
            "mimeType": "text/plain",
            "buffer": ATTACHMENT_BODY,
        }
    )
    # The handle is written once the upload has finished; submitting before it
    # exists would post the thread without its attachment.
    expect(
        page.locator('#edit-form input[type="hidden"][name="attachments"]')
    ).to_have_count(1, timeout=10_000)

    page.locator('#edit-form button[value="create"]').click()
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("Typed into the rich text editor.")).to_be_visible()
    link = page.get_by_role("link", name=ATTACHMENT_NAME).first
    expect(link).to_be_visible()

    response = page.request.get(link.get_attribute("href"))
    assert response.ok, response.status
    assert response.body() == ATTACHMENT_BODY
    js_errors.assert_clean("creating a thread with an attachment")


def test_the_editor_toolbar_survives_saving_and_editing(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """Everything on the toolbar has to get past the server's sanitiser, and a
    saved post has to come back into the editor with its formatting."""
    page = logged_in
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )
    page.fill("#title", "Formatting through the toolbar")

    def tool(command: str, level: int | None = None) -> Locator:
        suffix = f'[data-level="{level}"]' if level else ""
        return page.locator(f'[data-command="{command}"]{suffix}')

    editor = page.locator(EDITOR)
    editor.click()
    tool("toggleHeading", 2).click()
    editor.press_sequentially("A heading\n")
    tool("toggleBold").click()
    expect(tool("toggleBold")).to_have_attribute("aria-pressed", "true")
    editor.press_sequentially("loud")
    tool("toggleBold").click()
    editor.press_sequentially(" and ")
    tool("toggleItalic").click()
    editor.press_sequentially("slanted")
    tool("toggleItalic").click()
    editor.press_sequentially("\n")
    tool("toggleBulletList").click()
    editor.press_sequentially("an item\n\n")
    tool("toggleOrderedList").click()
    editor.press_sequentially("a step\n\n")
    tool("toggleBlockquote").click()
    editor.press_sequentially("a quote\n\n")
    page.once("dialog", lambda dialog: dialog.accept("https://example.com/page"))
    page.locator("[data-link-prompt]").click()

    page.locator('#edit-form button[value="create"]').click()
    page.wait_for_load_state("networkidle")

    def assert_formatted(root: str) -> None:
        expect(page.locator(f"{root} h2")).to_have_text("A heading")
        expect(page.locator(f"{root} strong")).to_have_text("loud")
        expect(page.locator(f"{root} em")).to_have_text("slanted")
        expect(page.locator(f"{root} ul li")).to_have_text("an item")
        expect(page.locator(f"{root} ol li")).to_have_text("a step")
        expect(page.locator(f"{root} blockquote")).to_have_text("a quote")
        expect(
            page.locator(f'{root} a[href="https://example.com/page"]')
        ).to_be_visible()

    assert_formatted(POST_BODY)

    page.locator('a[href$="/edit"]').first.click()
    page.wait_for_load_state("networkidle")
    assert_formatted(EDITOR)

    # The middle of the last paragraph is past its short text, so the caret goes to
    # the end. ProseMirror reads the selection just after mouseup; a key pressed
    # sooner than any person could would still go to the start of the document.
    page.locator(f"{EDITOR} p").last.click()
    page.wait_for_timeout(100)
    page.keyboard.press("Enter")
    page.keyboard.type("Added later.")
    page.locator('#edit-form button[type="submit"]').first.click()
    page.wait_for_load_state("networkidle")

    assert_formatted(POST_BODY)
    expect(page.locator(POST_BODY)).to_contain_text("Added later.")
    js_errors.assert_clean("formatting a post")


def test_text_that_looks_like_html_stays_text_when_edited(
    logged_in: Page, base_url: str
) -> None:
    """The textarea is where a saved post re-enters the editor. Written there
    unescaped, `&lt;b&gt;` came back as a real tag."""
    page = logged_in
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )
    page.fill("#title", "Writing about markup")
    page.locator(EDITOR).click()
    page.locator(EDITOR).press_sequentially("Use <b>this</b> tag")
    page.locator('#edit-form button[value="create"]').click()
    page.wait_for_load_state("networkidle")

    page.locator('a[href$="/edit"]').first.click()
    page.wait_for_load_state("networkidle")

    expect(page.locator(EDITOR)).to_have_text("Use <b>this</b> tag")
    expect(page.locator(f"{EDITOR} b, {EDITOR} strong")).to_have_count(0)


def test_a_message_emptied_in_the_editor_is_refused(
    logged_in: Page, base_url: str
) -> None:
    """An empty document serialises as `<p></p>`, which is not an empty string
    and would have passed the required validator."""
    page = logged_in
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )
    page.fill("#title", "This thread must not be created")
    editor = page.locator(EDITOR)
    editor.click()
    editor.press_sequentially("x")
    page.keyboard.press("Backspace")

    page.locator('#edit-form button[value="create"]').click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(re.compile(r"/new_thread/"))
    expect(page.locator(EDITOR)).to_be_visible()


def test_a_message_can_be_posted_without_the_editor(
    logged_in: Page, base_url: str
) -> None:
    """If the editor fails to load, the plain field is still there."""
    page = logged_in
    page.route(re.compile(r"/editor\.js"), lambda route: route.abort())
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )
    expect(page.locator(".ads-editor")).to_be_hidden()

    page.fill("#title", "Posted through the plain field")
    page.fill("#message", "<p>No editor <em>here</em>.</p>")
    page.locator('#edit-form button[value="create"]').click()
    page.wait_for_load_state("networkidle")

    expect(page.locator(f"{POST_BODY} em")).to_have_text("here")


def test_a_wiki_page_is_created_then_edited(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The body is Markdown in a plain textarea; what comes back is rendered.

    Editing posts the page's last revision id, which the server compares to
    detect a concurrent edit, so the second submit exercises that check on the
    path where it must let the edit through.
    """
    page = logged_in
    wiki = f"{base_url}/communities/{COMMUNITY}/wiki"
    page.goto(f"{wiki}/new", wait_until="networkidle")

    page.fill('#edit-form input[name="title"]', "Written in the browser")
    page.fill('#edit-form textarea[name="body_src"]', "First **draft**.")
    page.locator('#edit-form button[value="create"]').click()
    page.wait_for_load_state("networkidle")

    expect(page.locator("strong", has_text="draft")).to_be_visible()

    page.goto(f"{wiki}/edit?title=Written+in+the+browser", wait_until="networkidle")
    page.fill('#edit-form textarea[name="body_src"]', "Second *revision*.")
    page.fill('#edit-form input[name="message"]', "edited end to end")
    page.locator('#edit-form button[type="submit"]').first.click()
    page.wait_for_load_state("networkidle")

    expect(page.locator("em", has_text="revision")).to_be_visible()
    expect(page.get_by_text("First")).to_have_count(0)
    js_errors.assert_clean("creating and editing a wiki page")


def test_a_user_photo_is_uploaded(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """The image widget is built on the same upload widget, and broke with it."""
    page = logged_in
    png = BytesIO()
    Image.new("RGB", (8, 8), "red").save(png, "PNG")

    page.goto(f"{base_url}/preferences/user", wait_until="networkidle")
    before = page.request.get(f"{base_url}/users/1/photo").body()

    page.locator('#account-form input[type="file"]').set_input_files(
        {"name": "me.png", "mimeType": "image/png", "buffer": png.getvalue()}
    )
    expect(
        page.locator('#account-form input[type="hidden"][name="photo"]')
    ).to_have_count(1, timeout=10_000)
    expect(
        page.locator(
            "#account-form .file-item img, #account-form .file-item canvas"
        ).first
    ).to_be_visible()
    # The seeded administrator has no first name, which the account asks for.
    page.fill("#first_name", "Ada")
    page.locator('#account-form button[type="submit"]').click()
    page.wait_for_load_state("networkidle")

    after = page.request.get(f"{base_url}/users/1/photo")
    assert after.ok, after.status
    assert after.body() != before, "the photo did not change"
    js_errors.assert_clean("uploading a user photo")


def _text_file(name: str, body: bytes = b"content") -> dict:
    return {"name": name, "mimeType": "text/plain", "buffer": body}


def _alerts(page: Page) -> list[str]:
    """Record alert() messages; Playwright would dismiss them unseen otherwise."""
    messages: list[str] = []

    def on_dialog(dialog: Dialog) -> None:
        messages.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", on_dialog)
    return messages


def _record_progress_bars(page: Page) -> None:
    """A bar goes away when its upload ends, so note its widths while it lasts.

    In sessionStorage, because the folder dialog reloads the page at the end.
    """
    page.evaluate(
        """() => {
            new MutationObserver((mutations) => {
              for (const { target } of mutations) {
                if (target.getAttribute("role") === "progressbar") {
                  const widths = JSON.parse(sessionStorage.barWidths || "[]");
                  widths.push(target.style.width);
                  sessionStorage.barWidths = JSON.stringify(widths);
                }
              }
            }).observe(document.body, {
              subtree: true,
              attributes: true,
              attributeFilter: ["style"],
            });
        }"""
    )


def _recorded_progress_bars(page: Page) -> list[str]:
    return page.evaluate('JSON.parse(sessionStorage.barWidths || "[]")')


def _open_thread_form(page: Page, base_url: str) -> Locator:
    page.goto(
        f"{base_url}/communities/{COMMUNITY}/forum/new_thread/",
        wait_until="networkidle",
    )
    return page.locator('.js-file-button input[type="file"]')


def test_an_attachment_reports_its_progress(logged_in: Page, base_url: str) -> None:
    page = logged_in
    file_input = _open_thread_form(page, base_url)
    _record_progress_bars(page)

    file_input.set_input_files(_text_file("big.txt", b"x" * 5_000_000))
    expect(
        page.locator('#edit-form input[type="hidden"][name="attachments"]')
    ).to_have_count(1, timeout=30_000)

    assert "100%" in _recorded_progress_bars(page)


def test_a_form_cannot_be_posted_while_an_attachment_is_uploading(
    logged_in: Page, base_url: str
) -> None:
    """Posting then would silently lose the attachment."""
    page = logged_in
    alerts = _alerts(page)
    held: list[Route] = []

    def hold(route: Route) -> None:
        held.append(route)

    page.route(UPLOAD_URL, hold)
    file_input = _open_thread_form(page, base_url)
    page.fill("#title", "Posted too early")

    file_input.set_input_files(_text_file("slow.txt"))
    for _attempt in range(100):
        if held:
            break
        page.wait_for_timeout(50)
    assert held, "the upload never started"
    url = page.url
    page.locator('#edit-form button[value="create"]').click()

    assert page.url == url
    assert len(alerts) == 1

    held[0].continue_()
    expect(
        page.locator('#edit-form input[type="hidden"][name="attachments"]')
    ).to_have_count(1, timeout=10_000)


def test_a_failed_attachment_is_reported_and_dropped(
    logged_in: Page, base_url: str
) -> None:
    page = logged_in
    alerts = _alerts(page)
    page.route(UPLOAD_URL, lambda route: route.fulfill(status=500))
    file_input = _open_thread_form(page, base_url)

    file_input.set_input_files(_text_file("refused.txt"))

    expect(page.locator(".file-item")).to_have_count(0, timeout=10_000)
    assert len(alerts) == 1
    expect(
        page.locator('#edit-form input[type="hidden"][name="attachments"]')
    ).to_have_count(0)


def _open_new_folder(page: Page, base_url: str, title: str) -> None:
    """Upload into a folder of its own: other tests read the root listing."""
    page.goto(f"{base_url}/communities/{COMMUNITY}/docs/", wait_until="networkidle")
    page.locator('[data-modal-open="#modal-new-folder"]').first.click()
    modal = page.locator("#modal-new-folder")
    modal.locator('input[name="title"]').fill(title)
    modal.locator('button[type="submit"]').click()
    page.get_by_role("link", name=title).first.click()
    page.wait_for_load_state("networkidle")


def _open_upload_dialog(page: Page) -> Locator:
    page.locator('[data-modal-open="#modal-upload-files"]').first.click()
    dialog = page.locator("#modal-upload-files")
    expect(dialog).to_be_visible()
    return dialog


def test_files_are_uploaded_to_a_folder(
    logged_in: Page, base_url: str, js_errors: JSErrors
) -> None:
    """Pick several, change your mind about one, send the rest, each one whole."""
    page = logged_in
    _open_new_folder(page, base_url, "Upload target")
    dialog = _open_upload_dialog(page)
    send = dialog.locator(".js-upload")
    expect(send).to_be_hidden()

    picker = dialog.locator('input[type="file"]')
    picker.set_input_files([_text_file("first.txt", b"first body")])
    picker.set_input_files(
        [_text_file("second.txt", b"second body"), _text_file("dropped.txt")]
    )
    row = dialog.locator("li", has_text="dropped.txt")
    expect(row).to_be_visible()
    expect(dialog.locator("li", has_text="first.txt")).to_be_visible()
    row.locator("button").click()
    expect(row).to_have_count(0)

    _record_progress_bars(page)
    send.click()

    for name, body in (("first.txt", b"first body"), ("second.txt", b"second body")):
        link = page.locator('a[href*="/docs/doc/"]', has_text=name).first
        expect(link).to_be_attached(timeout=10_000)
        response = page.request.get(f"{link.get_attribute('href')}/download")
        assert response.ok, response.status
        assert response.body() == body
    expect(page.locator('a[href*="/docs/doc/"]', has_text="dropped.txt")).to_have_count(
        0
    )
    assert "100%" in _recorded_progress_bars(page)
    js_errors.assert_clean("uploading files to a folder")


def test_an_uploaded_zip_is_unpacked_when_asked(logged_in: Page, base_url: str) -> None:
    """The checkbox is a form field, sent alongside each file."""
    page = logged_in
    archive = BytesIO()
    with ZipFile(archive, "w") as zipfile:
        zipfile.writestr("inner/unpacked.txt", "from the archive")
    _open_new_folder(page, base_url, "Zip target")
    dialog = _open_upload_dialog(page)

    dialog.locator('input[type="file"]').set_input_files(
        {
            "name": "bundle.zip",
            "mimeType": "application/zip",
            "buffer": archive.getvalue(),
        }
    )
    dialog.locator('input[name="uncompress_files"]').check()
    dialog.locator(".js-upload").click()

    expect(page.get_by_role("link", name="inner").first).to_be_attached(timeout=10_000)
    expect(page.locator('a[href*="/docs/doc/"]', has_text="bundle.zip")).to_have_count(
        0
    )


def test_cancelling_the_upload_dialog_forgets_the_selection(
    logged_in: Page, base_url: str
) -> None:
    page = logged_in
    _open_new_folder(page, base_url, "Cancel target")
    dialog = _open_upload_dialog(page)
    dialog.locator('input[type="file"]').set_input_files(_text_file("forgotten.txt"))
    row = dialog.locator("li", has_text="forgotten.txt")
    expect(row).to_be_visible()

    dialog.locator("[data-modal-close]").first.click()
    expect(dialog).to_be_hidden()
    _open_upload_dialog(page)

    expect(row).to_have_count(0)
    expect(dialog.locator(".js-upload")).to_be_hidden()


def test_a_file_the_server_refuses_says_why_and_keeps_the_dialog_open(
    logged_in: Page, base_url: str
) -> None:
    page = logged_in
    _open_new_folder(page, base_url, "Refusal target")
    url = page.url

    def refuse_uploads(route: Route) -> None:
        if route.request.method == "POST":
            route.fulfill(status=413)
        else:
            route.continue_()

    page.route(re.compile(r"/docs/folder/\d+"), refuse_uploads)
    dialog = _open_upload_dialog(page)
    dialog.locator('input[type="file"]').set_input_files(_text_file("huge.txt"))
    dialog.locator(".js-upload").click()

    expect(dialog.get_by_text("maximum file size exceeded")).to_be_visible(
        timeout=10_000
    )
    expect(dialog).to_be_visible()
    assert page.url == url
