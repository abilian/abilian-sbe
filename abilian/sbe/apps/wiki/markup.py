"""
Set up the markdown converter. Add extensions here (for now).
"""
from flask import url_for
import markdown

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
  ctx = {}
  ctx['extensions'] = ['wikilinks', 'toc']
  ctx['extension_configs'] = {'wikilinks' : [('build_url', build_url)]}
  ctx['output_format'] = 'html5'
  md = markdown.Markdown(**ctx)
  return md.convert(text)
