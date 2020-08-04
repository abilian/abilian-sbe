from unittest import mock
from urllib.parse import quote_plus

import pytest
from flask_login import current_user
from markdown import Markdown

from abilian.sbe.apps.wiki.markup import SBEWikiLinkExtension
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.testing.util import client_login


@pytest.mark.parametrize("text", ["TOTO", "x 123", "/#$", "/*€("])
def test_wikilink_extension(text, db, req_ctx):
    qtext = str(quote_plus(text.encode("utf-8")))
    wikilink = "[[" + text + "]]"

    def build_url(label: str, base: str, end: str) -> str:
        print("build_url called")
        return "/?title=" + quote_plus(label.encode("utf-8")) + end

    extension = SBEWikiLinkExtension(build_url=build_url)
    ctx = {
        "extensions": [extension, "markdown.extensions.toc"],
        "output_format": "html5",
    }
    md = Markdown(**ctx)

    def check(page_exists: bool) -> None:
        page_exists_mock = mock.MagicMock(return_value=page_exists)
        with mock.patch("abilian.sbe.apps.wiki.markup.page_exists", page_exists_mock):
            result = md.convert(wikilink)

        if page_exists:
            expected_tpl = (
                '<p><a class="wikilink" href="/?title={href}/">{text}</a></p>'
            )
        else:
            expected_tpl = (
                '<p><a class="wikilink new" href="/?title={href}/">{text}</a></p>'
            )

        expected = expected_tpl.format(href=qtext, text=text)
        assert expected == result

    check(True)
    check(False)


def test_new_page(user, client, req_ctx):
    with client:
        with client_login(client, user):
            print(current_user)
            page = WikiPage(title="Some page", body_src="abc")
            assert page.title == "Some page"
            assert page.name == "Some page"
            assert page.body_src == "abc"
            assert page.body_html == "<p>abc</p>"
            assert len(page.revisions) == 1

            revision = page.revisions[0]
            assert revision.number == 0
            assert revision.author == user


def test_rename_page(user, req_ctx):
    page = WikiPage(title="Some page", body_src="abc")
    assert page.title == "Some page"
    assert page.name == "Some page"

    page.title = "Title Renamed"
    assert page.title == "Title Renamed"
    assert page.name == "Title Renamed"

    page.name = "Name"
    assert page.title == "Name"
    assert page.name == "Name"


def test_create_revision(user, client, req_ctx):
    with client:
        with client_login(client, user):
            page = WikiPage("abc")
            page.create_revision("def", "page updated")

            assert len(page.revisions) == 2
            last_revision = page.revisions[1]
            assert last_revision.number == 1
            assert last_revision.author == user
