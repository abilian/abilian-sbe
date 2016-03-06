# coding=utf-8
"""
Set up the markdown converter. Add extensions here (for now).
"""
from __future__ import absolute_import

import markdown
from flask import url_for
from markdown.extensions.wikilinks import WikiLinkExtension, WikiLinks
from markdown.util import etree

__all__ = ['convert']


class UrlBuilder(object):

    def __init__(self, page):
        self.page = page

    def build(self, label, base, end):
        label = label.strip()
        return url_for(".page",
                       community_id=self.page.community.slug,
                       title=label)


def convert(page, text):
    build_url = UrlBuilder(page).build
    extension = SBEWikiLinkExtension([('build_url', build_url)])
    ctx = {}
    ctx['extensions'] = [extension, 'toc']
    ctx['output_format'] = 'html5'
    md = markdown.Markdown(**ctx)
    return md.convert(text)


class SBEWikiLinkExtension(WikiLinkExtension):

    def extendMarkdown(self, md, md_globals):
        self.md = md

        # append to end of inline patterns
        WIKILINK_RE = r'\[\[(.*?)\]\]'
        wikilinkPattern = SBEWikiLinks(WIKILINK_RE, self.getConfigs())
        wikilinkPattern.md = md
        md.inlinePatterns.add('wikilink', wikilinkPattern, "<not_strong")


class SBEWikiLinks(WikiLinks):

    def handleMatch(self, m):
        from .forms import page_exists
        if m.group(2).strip():
            base_url, end_url, html_class = self._getMeta()
            label = m.group(2).strip()
            url = self.config['build_url'](label, base_url, end_url)
            a = etree.Element('a')
            a.text = label
            a.set('href', url)
            if html_class:
                if page_exists(label):
                    a.set('class', html_class)
                else:
                    a.set('class', html_class + ' new')
        else:
            a = ''
        return a
