"""Set up the markdown converter.

Add extensions here (for now).
"""
import markdown
from flask import url_for
from markdown.core import Markdown
from markdown.extensions.wikilinks import WikiLinkExtension, \
    WikiLinksInlineProcessor
from markdown.util import etree

from abilian.sbe.apps.wiki.models import WikiPage

from .util import page_exists

__all__ = ("convert", "SBEWikiLinkExtension")


class UrlBuilder:
    def __init__(self, page: WikiPage) -> None:
        self.page = page

    def build(self, label: str, base: str, end: str) -> str:
        label = label.strip()
        return url_for(".page", community_id=self.page.community.slug, title=label)


def convert(page: WikiPage, text: str) -> str:
    build_url = UrlBuilder(page).build
    extension = SBEWikiLinkExtension(build_url=build_url)
    ctx = {
        "extensions": [extension, "markdown.extensions.toc"],
        "output_format": "html5",
    }
    md = markdown.Markdown(**ctx)
    return md.convert(text)


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
            a = etree.Element("a")
            a.text = label
            a.set("href", url)
            if html_class:
                if page_exists(label):
                    a.set("class", html_class)
                else:
                    a.set("class", html_class + " new")
        else:
            a = ""
        return a, m.start(0), m.end(0)
