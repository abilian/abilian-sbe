# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from unittest import mock
from urllib.parse import quote_plus

import pytest
from markdown import Markdown

from abilian.sbe.apps.wiki.markup import SBEWikiLinkExtension
from abilian.sbe.apps.wiki.models import WikiPage, WikiPageRevision
from tests.util import client_login, login


@pytest.mark.parametrize("text", ["TOTO", "x 123", "/#$", "/*€("])
def test_wikilink_extension(text, db) -> None:
    qtext = str(quote_plus(text.encode("utf-8")))
    wikilink = f"[[{text}]]"

    def build_url(label: str, base: str, end: str) -> str:
        print("build_url called")
        return f"/?title={quote_plus(label.encode('utf-8'))}{end}"

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


def test_new_page(user, client) -> None:
    with client_login(client, user):
        page = WikiPage(title="Some page", body_src="abc")
        assert page.title == "Some page"
        assert page.name == "Some page"
        assert page.body_src == "abc"
        assert page.body_html == "<p>abc</p>"
        assert len(page.revisions) == 1

        revision = page.revisions[0]
        assert revision.number == 0
        assert revision.author == user


def test_rename_page(user) -> None:
    page = WikiPage(title="Some page", body_src="abc")
    assert page.title == "Some page"
    assert page.name == "Some page"

    page.title = "Title Renamed"
    assert page.title == "Title Renamed"
    assert page.name == "Title Renamed"

    page.name = "Name"
    assert page.title == "Name"
    assert page.name == "Name"


def test_create_revision(user, client) -> None:
    with client_login(client, user):
        page = WikiPage("abc")
        page.create_revision("def", "page updated")

        assert len(page.revisions) == 2
        last_revision = page.revisions[1]
        assert last_revision.number == 1
        assert last_revision.author == user


def test_a_new_revision_is_saved(db, community1) -> None:
    with login(community1.test_user):
        page = WikiPage(title="Saved", body_src="first", community=community1)
        db.session.add(page)
        db.session.flush()

        page.create_revision("second", "edit")
        db.session.commit()

    revisions = WikiPageRevision.query.filter(WikiPageRevision.page_id == page.id)
    assert revisions.count() == 2
