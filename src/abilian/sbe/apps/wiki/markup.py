# Copyright (c) 2012-2024, Abilian SAS

"""A wiki page's Markdown made HTML: links between pages, ids on headings, and only
the tags Markdown writes, so that no one runs a script in the browsers of those who
read their page."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

import bleach
import markdown
from flask import url_for
from markdown.extensions.wikilinks import WikiLinkExtension, WikiLinksInlineProcessor

from .util import page_exists

if TYPE_CHECKING:
    from markdown.core import Markdown

    from abilian.sbe.apps.communities.models import Community

__all__ = ("SBEWikiLinkExtension", "convert")

#: What Markdown writes; anything else written by hand is dropped, its text kept.
ALLOWED_TAGS = frozenset(
    {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "code",
        "dd",
        "del",
        "div",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)

ALLOWED_ATTRIBUTES = {
    "*": ["id", "title"],
    "a": ["href", "title", "class"],
    "div": ["class"],
    "img": ["src", "alt", "title"],
}


class UrlBuilder:
    def __init__(self, community: Community) -> None:
        self.community = community

    def build(self, label: str, base: str, end: str) -> str:
        label = label.strip()
        return url_for(".page", community_id=self.community.slug, title=label)


def convert(community: Community, text: str) -> str:
    """`text`, in Markdown, as a page of `community`'s wiki shows it."""
    build_url = UrlBuilder(community).build
    extension = SBEWikiLinkExtension(build_url=build_url)
    ctx = {
        "extensions": [extension, "markdown.extensions.toc"],
        "output_format": "html5",
    }
    md = markdown.Markdown(**ctx)
    return bleach.clean(
        md.convert(text), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
    )


class SBEWikiLinkExtension(WikiLinkExtension):
    def extendMarkdown(self, md: Markdown) -> None:
        # self.md = md

        # append to end of inline patterns
        WIKILINK_RE = r"\[\[(.*?)\]\]"
        wikilinkPattern = SBEWikiLinksInlineProcessor(WIKILINK_RE, self.getConfigs())
        wikilinkPattern.md = md
        md.inlinePatterns.register(wikilinkPattern, "wikilink", 75)


class SBEWikiLinksInlineProcessor(WikiLinksInlineProcessor):
    def handleMatch(self, m, data):
        label = m.group(1).strip()
        if label:
            base_url, end_url, html_class = self._getMeta()
            url = self.config["build_url"](label, base_url, end_url)
            a = Element("a")
            a.text = label
            a.set("href", url)
            if html_class:
                if page_exists(label):
                    a.set("class", html_class)
                else:
                    a.set("class", f"{html_class} new")
        else:
            a = ""
        return a, m.start(0), m.end(0)
