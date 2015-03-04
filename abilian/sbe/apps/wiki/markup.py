# coding=utf-8
"""
Set up the markdown converter. Add extensions here (for now).
"""
from __future__ import absolute_import

from flask import url_for
import markdown
from markdown.extensions.wikilinks import WikiLinkExtension, WikiLinks
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
    wikilinkPattern = WikiLinks(WIKILINK_RE, self.getConfigs())
    wikilinkPattern.md = md
    md.inlinePatterns.add('wikilink', wikilinkPattern, "<not_strong")
