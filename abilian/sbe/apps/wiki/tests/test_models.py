# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals

from flask import g
from markdown import Markdown
from mock import MagicMock, patch
from six import text_type
from six.moves.urllib.parse import quote_plus

from abilian.sbe.apps.wiki.markup import SBEWikiLinkExtension
from abilian.sbe.apps.wiki.models import WikiPage

pytest_plugins = ["abilian.sbe.apps.communities.tests.fixtures"]


def test_wikilink_extension():
    text = "/*€("
    wikilink = "[[" + text + "]]"

    def build_url(label, base, end):
        return "/?title=" + quote_plus(label.encode("utf-8")) + end

    extension = SBEWikiLinkExtension([("build_url", build_url)])
    ctx = {}
    ctx["extensions"] = [extension, "toc"]
    ctx["output_format"] = "html5"
    md = Markdown(**ctx)

    page_exists_mock = MagicMock(return_value=True)
    with patch("abilian.sbe.apps.wiki.forms.page_exists", page_exists_mock):
        result = md.convert(wikilink)

    qtext = text_type(quote_plus(text.encode("utf-8")))
    expected = '<p><a class="wikilink" href="/?title={href}/">{text}</a></p>'
    expected = expected.format(href=qtext, text=text)
    assert expected == result

    # make sur the class is 'wikilink new' if page exists'
    page_exists_mock = MagicMock(return_value=False)
    with patch("abilian.sbe.apps.wiki.forms.page_exists", page_exists_mock):
        result = md.convert(wikilink)

    qtext = text_type(quote_plus(text.encode("utf-8")))
    expected = '<p><a class="wikilink new" href="/?title={href}/">{text}</a></p>'
    expected = expected.format(href=qtext, text=text)
    assert expected == result


def test_new_page(user, req_ctx):
    g.user = user

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
    g.user = user

    page = WikiPage(title="Some page", body_src="abc")
    assert page.title == "Some page"
    assert page.name == "Some page"

    page.title = "Title Renamed"
    assert page.title == "Title Renamed"
    assert page.name == "Title Renamed"

    page.name = "Name"
    assert page.title == "Name"
    assert page.name == "Name"


def test_create_revision(user, req_ctx):
    g.user = user

    page = WikiPage("abc")
    page.create_revision("def", "page updated")

    assert len(page.revisions) == 2
    last_revision = page.revisions[1]
    assert last_revision.number == 1
    assert last_revision.author == user
