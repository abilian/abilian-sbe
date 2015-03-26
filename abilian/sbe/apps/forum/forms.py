# coding=utf-8
"""
"""
from __future__ import absolute_import

import bleach
from flask.ext.babel import lazy_gettext as _l
from wtforms import TextAreaField, StringField, BooleanField
from abilian.web.forms import Form, RichTextWidget
from abilian.web.forms.validators import required, optional
from abilian.web.forms.filters import strip
from abilian.web.forms.fields import FileField


ALLOWED_TAGS = [
    'a',
    'abbr',
    'acronym',
    'b',
    'blockquote',
    'br',
    'code',
    'em',
    'i',
    'li',
    'ol',
    'strong',
    'ul',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'p',
    'u',
    'img',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
    'img': ['src'],
}

WIDGET_ALLOWED = {}
for attr in ALLOWED_TAGS:
  allowed = ALLOWED_ATTRIBUTES.get(attr, True)
  if not isinstance(allowed, bool):
    allowed = {tag: True for tag in allowed}
  WIDGET_ALLOWED[attr] = allowed


class ThreadForm(Form):
  title = StringField(label=_l(u"Title"),
                      filters=(strip,),
                      validators=[required()])
  message = TextAreaField(label=_l(u"Message"),
                          widget=RichTextWidget(allowed_tags=WIDGET_ALLOWED),
                          filters=(strip,),
                          validators=[required()])
  attachments = FileField(label=_l(u'Attachments'), multiple=True,
                          validators=[optional()])
  send_by_email = BooleanField(label=_l(u"Send by email?"), default=True)

  def validate_message(self, field):
    field.data = bleach.clean(field.data, tags=ALLOWED_TAGS,
                              attributes=ALLOWED_ATTRIBUTES, strip=True)


class CommentForm(Form):
  message = TextAreaField(label=_l("Message"),
                          widget=RichTextWidget(allowed_tags=WIDGET_ALLOWED),
                          filters=(strip,),
                          validators=[required()])
  attachments = FileField(label=_l(u'Attachments'), multiple=True,
                          validators=[optional()])
  send_by_email = BooleanField(label=_l(u"Send by email?"), default=True)

  def validate_message(self, field):
    field.data = bleach.clean(field.data, tags=ALLOWED_TAGS,
                              attributes=ALLOWED_ATTRIBUTES, strip=True)
