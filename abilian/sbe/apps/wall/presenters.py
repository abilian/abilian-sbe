# coding=utf-8
"""
"""
from __future__ import absolute_import

import traceback
import bleach
from jinja2 import Template, Markup
from flask.ext.babel import gettext as _, lazy_gettext as _l

from abilian.core.util import BasePresenter
from abilian.web.util import url_for

from abilian.sbe.apps.communities.models import Community
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.forum.models import Post, Thread
from abilian.sbe.apps.wiki.models import WikiPage


# Poor man's pattern matching.
MESSAGES = {
  ('post', Thread): _l(u'has started conversation "{object}"'),
  ('post', Post): _l(u'has participated in conversation "{object}"'),
  ('post', Document): _l(u'has published document "{object}"'),
  ('post', WikiPage): _l(u'has created wiki page "{object}"'),

  ('update', Document): _l(u'has updated document "{object}"'),
  ('update', WikiPage): _l(u'has updated wiki page "{object}"'),

  ('join', Community): _l(u'has joined the community {object}.'),
  ('leave', Community): _l(u'has left the community {object}.'),
}

OBJ_TEMPLATE = Template(
  u'<a href="{{ object_url|safe }}">{{ object_name }}</a>'
)

class ActivityEntryPresenter(BasePresenter):
  @property
  def object_url(self):
    return url_for(self._model.object)

  def message(self, ignore_community=False):
    try:
      # another quick&dirty approach for now. FIXME later.
      entry = self._model
      object_class = entry.object_type.split('.')[-1]
      object_class_localized = _(object_class)

      ctx = {}
      ctx['verb'] = entry.verb

      ctx['object_name'] = entry.object.name
      ctx['object_url'] = url_for(entry.object)
      ctx['object_type'] = object_class_localized
      ctx['object'] = OBJ_TEMPLATE.render(**ctx)

      if entry.target:
        ctx['target_name'] = entry.target.name
        ctx['target_url'] = url_for(entry.target)
        ctx['target'] = OBJ_TEMPLATE.render(
          object_name=ctx['target_name'],
          object_url=ctx['target_url']
        )

      msg = MESSAGES.get((entry.verb, entry.object.__class__))
      if msg:
        msg = msg.format(**ctx)
        if entry.target and not ignore_community:
          msg += _(u' in the community {target}.').format(**ctx)
        else:
          msg += u"."

      elif entry.verb == 'post':
        msg = _(u'has posted an object of type {object_type} '
                u'called "{object}"').format(**ctx)

        if entry.target and not ignore_community:
          msg += _(u' in the community {target}.').format(**ctx)
        else:
          msg += u"."

      elif entry.verb == 'join':
        msg = _(u'has joined the community {object}.').format(**ctx)

      elif entry.verb == 'leave':
        msg = _(u'has left the community {object}.').format(**ctx)

      else:
        msg = _(u'has done action "{verb}" on object "{object}".').format(**ctx)

      return Markup(msg)

    except:
      traceback.print_exc()
      raise

  def body(self):
    if isinstance(self.object, Thread):
      body = bleach.clean(self.object.posts[0].body_html, tags=[], strip=True)
      if len(body) > 400:
        body = body[0:400] + u"…"
      return body
    elif isinstance(self.object, Post):
      body = bleach.clean(self.object.body_html, tags=[], strip=True)
      if len(body) > 400:
        body = body[0:400] + u"…"
      return body
    else:
      return ""
