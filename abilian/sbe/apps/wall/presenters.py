import logging
from functools import singledispatch

import bleach
from flask import render_template_string
from jinja2 import Markup, Template

from abilian.core.util import BasePresenter
from abilian.i18n import _, _l
from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.models import Community
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.forum.models import Post, Thread
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.web.util import url_for

logger = logging.getLogger(__name__)

# Poor man's pattern matching.
MESSAGES = {
    ("post", Thread): _l('has started conversation "{object}"'),
    ("post", Post): _l('has participated in conversation "{object}"'),
    ("post", Document): _l('has published document "{object}"'),
    ("post", WikiPage): _l('has created wiki page "{object}"'),
    ("post", Event): _l('has published event "{object}"'),
    ("post", Community): _l('has created communauté "{object}"'),
    #
    ("update", Document): _l('has updated document "{object}"'),
    ("update", WikiPage): _l('has updated wiki page "{object}"'),
    ("update", Community): _l('has updated community "{object}"'),
    #
    ("join", Community): _l("has joined the community {object}."),
    #
    ("leave", Community): _l("has left the community {object}."),
}

OBJ_TEMPLATE = Template('<a href="{{ object_url|safe }}">{{ object_name }}</a>')

POST_BODY_TEMPLATE = """
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
"""

DOCUMENT_BODY_TEMPLATE = """
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
"""


class ActivityEntryPresenter(BasePresenter):
    @property
    def object_url(self):
        return url_for(self._model.object)

    def message(self, ignore_community=False) -> Markup:
        try:
            # another quick&dirty approach for now. FIXME later.
            entry = self._model
            object_class = entry.object_type.split(".")[-1]
            object_class_localized = _(object_class)

            ctx = {}
            ctx["verb"] = entry.verb

            ctx["object_name"] = entry.object.name or getattr(
                entry.object, "title", "???"
            )
            ctx["object_url"] = url_for(entry.object)
            ctx["object_type"] = object_class_localized
            ctx["object"] = OBJ_TEMPLATE.render(**ctx)

            if entry.target:
                ctx["target_name"] = entry.target.name
                ctx["target_url"] = url_for(entry.target)
                ctx["target"] = OBJ_TEMPLATE.render(
                    object_name=ctx["target_name"], object_url=ctx["target_url"]
                )

            msg = MESSAGES.get((entry.verb, entry.object.__class__))
            if msg:
                msg = msg.format(**ctx)
                if entry.target and not ignore_community:
                    msg += " " + _("in the community {target}.").format(**ctx)
                else:
                    msg += "."

            elif entry.verb == "post":
                msg = _(
                    "has posted an object of type {object_type} " 'called "{object}"'
                ).format(**ctx)

                if entry.target and not ignore_community:
                    msg += " " + _("in the community {target}.").format(**ctx)
                else:
                    msg += "."

            elif entry.verb == "join":
                msg = _("has joined the community {object}.").format(**ctx)

            elif entry.verb == "leave":
                msg = _("has left the community {object}.").format(**ctx)

            elif entry.verb == "update":
                msg = _("has updated {object_type} {object}.").format(**ctx)

            else:
                msg = _('has done action "{verb}" on object "{object}".').format(**ctx)

            return Markup(msg)

        except BaseException:
            logger.exception("Exception while presenting activity message")
            raise

    @property
    def body(self):
        return get_body(self.object)


@singledispatch
def get_body(object):
    return ""


@get_body.register(Thread)
def get_body_thread(object: Thread) -> Markup:
    body = bleach.clean(object.posts[0].body_html, tags=[], strip=True)
    body = Markup(body).unescape()
    if len(body) > 400:
        body = body[0:400] + "…"
    body = render_template_string(
        POST_BODY_TEMPLATE, object_url=url_for(object), body=body, post=object.posts[0]
    )
    return Markup(body)


@get_body.register(Post)
def get_body_post(object: Post) -> Markup:
    body = bleach.clean(object.body_html, tags=[], strip=True)
    body = Markup(body).unescape()
    if len(body) > 400:
        body = body[0:400] + "…"
    body = render_template_string(
        POST_BODY_TEMPLATE, object_url=url_for(object), body=body, post=object
    )
    return Markup(body)


@get_body.register(Document)
def get_body_document(object: Document) -> Markup:
    body = bleach.clean(object.body_html, tags=[], strip=True)
    body = Markup(body).unescape()
    if len(body) > 400:
        body = body[0:400] + "…"
    body = render_template_string(
        DOCUMENT_BODY_TEMPLATE, object_url=url_for(object), body=body, post=object
    )
    return Markup(body)
