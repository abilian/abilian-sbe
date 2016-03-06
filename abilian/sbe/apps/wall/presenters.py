# coding=utf-8
"""
"""
from __future__ import absolute_import

import logging

import bleach
from flask import render_template_string
from jinja2 import Markup, Template

from abilian.core.util import BasePresenter
from abilian.i18n import _, _l
from abilian.sbe.apps.communities.models import Community
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.documents.views.util import \
    breadcrumbs_for as doc_breadcrumb
from abilian.sbe.apps.forum.models import Post, Thread
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.web.util import url_for

logger = logging.getLogger(__name__)

# Poor man's pattern matching.
MESSAGES = {
    ('post', Thread): _l(u'has started conversation "{object}"'),
    ('post', Post): _l(u'has participated in conversation "{object}"'),
    ('post', Document): _l(u'has published document "{object}"'),
    ('post', WikiPage): _l(u'has created wiki page "{object}"'),
    ('update', Document): _l(u'has updated document "{object}"'),
    ('update', WikiPage): _l(u'has updated wiki page "{object}"'),
    ('update', Community): _l(u'has updated community "{object}"'),
    ('join', Community): _l(u'has joined the community {object}.'),
    ('leave', Community): _l(u'has left the community {object}.'),
}

OBJ_TEMPLATE = Template(
    u'<a href="{{ object_url|safe }}">{{ object_name }}</a>')

POST_BODY_TEMPLATE = u'''
  <span class="body">"<a href="{{ object_url |safe }}">{{ body }}</a>"
  {%- if post.attachments %}
  <div id="attachments">
    <ul>
      {%- for attachment in post.attachments %}
      <li>
        <span class="attachment-item">
          <img src="{{ attachment.icon }}""
              alt=""/>
          <a href="{{ url_for(attachment) }}">{{ attachment.name }}</a>
          ({{ attachment.content_length|filesize }})
        </span>
      </li>
      {%- endfor %}
    </ul>
  </div>
  {%- endif %}
  </span>
 '''

DOCUMENT_BODY_TEMPLATE = u'''
<div class="body">
  <div>
    <img src="{{ obj.icon }}" style="vertical-align: middle;" alt=""/>
    {% for p in parents[:-1] %}
    <a href="{{ p.path }}">{{ p.label }}</a> <span class="divider">/</span>
    {% endfor %}

    <a href="{{ url_for(obj) }}">{{ obj.name }}</a>
  </div>
  <div>
  {%- if obj.antivirus_ok %}
    <a href="{{ url_for('documents.document_download',
                         community_id=obj.community.slug,
                         doc_id=obj.id,
                         attach=True) }}">
      <i class="glyphicon glyphicon-download"></i>
      {{ _('Download') }} (<small>{{ obj.content_length|filesize  }}</small>)
    </a>
  {%- endif %}
  </div>
</div>
'''


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
                    object_url=ctx['target_url'])

            msg = MESSAGES.get((entry.verb, entry.object.__class__))
            if msg:
                msg = msg.format(**ctx)
                if entry.target and not ignore_community:
                    msg += u" " + _(u'in the community {target}.').format(**ctx)
                else:
                    msg += u"."

            elif entry.verb == 'post':
                msg = _(u'has posted an object of type {object_type} '
                        u'called "{object}"').format(**ctx)

                if entry.target and not ignore_community:
                    msg += u" " + _(u'in the community {target}.').format(**ctx)
                else:
                    msg += u"."

            elif entry.verb == 'join':
                msg = _(u'has joined the community {object}.').format(**ctx)

            elif entry.verb == 'leave':
                msg = _(u'has left the community {object}.').format(**ctx)

            elif entry.verb == 'update':
                msg = _(u'has updated {object_type} {object}.').format(**ctx)

            else:
                msg = _(u'has done action "{verb}" on object "{object}".').format(**ctx)

            return Markup(msg)

        except:
            logger.exception('Exception while presenting activity message')
            raise

    @property
    def body(self):
        if isinstance(self.object, Thread):
            body = bleach.clean(self.object.posts[0].body_html,
                                tags=[],
                                strip=True)
            body = Markup(body).unescape()
            if len(body) > 400:
                body = body[0:400] + u"…"
            body = render_template_string(POST_BODY_TEMPLATE,
                                          object_url=self.object_url,
                                          body=body,
                                          post=self.object.posts[0])
            return Markup(body)
        elif isinstance(self.object, Post):
            body = bleach.clean(self.object.body_html, tags=[], strip=True)
            body = Markup(body).unescape()
            if len(body) > 400:
                body = body[0:400] + u"…"
            body = render_template_string(POST_BODY_TEMPLATE,
                                          object_url=self.object_url,
                                          body=body,
                                          post=self.object)
            return Markup(body)
        elif isinstance(self.object, Document):
            parents = doc_breadcrumb(self.object)
            body = render_template_string(DOCUMENT_BODY_TEMPLATE,
                                          obj=self.object,
                                          parents=parents)
            return Markup(body)
        else:
            return ""
