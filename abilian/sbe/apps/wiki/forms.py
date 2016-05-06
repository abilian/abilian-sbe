# coding=utf-8
"""
Forms for the Wiki module.
"""
from __future__ import absolute_import

from flask import g
from wtforms import HiddenField, StringField, TextAreaField
from wtforms.validators import ValidationError, required

from abilian.i18n import _, _l
from abilian.web.forms import Form
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import flaghidden
from abilian.web.forms.widgets import TextArea

from .models import WikiPage


def clean_up(src):
    """Form filter."""
    src = src.replace("\r", "")
    return src


def int_or_none(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


class WikiPageForm(Form):
    title = StringField(label=_l(u"Title"),
                        filters=(strip,),
                        validators=[required()])
    body_src = TextAreaField(
        label=_l("Body"),
        filters=(strip, clean_up),
        validators=[required()],
        widget=TextArea(rows=10, resizeable='vertical'),)

    message = StringField(label=_l("Commit message"))
    page_id = HiddenField(filters=(int_or_none,), validators=[flaghidden()])
    last_revision_id = HiddenField(filters=(int_or_none,),
                                   validators=[flaghidden()])

    def validate_title(self, field):
        title = field.data
        if title != field.object_data and page_exists(title):
            raise ValidationError(
                _(u"A page with this name already exists. Please use another name.")
            )

    def validate_last_revision_id(self, field):
        val = field.data
        current = field.object_data

        if val is None or current is None:
            return

        if val != current:
            raise ValidationError(_(u'this page has been edited since'))


def page_exists(title):
    title = title.strip()
    return WikiPage.query \
               .filter(WikiPage.community_id == g.community.id,
                       WikiPage.title == title) \
               .count() > 0


# Not used yet
class CommentForm(Form):
    message = TextAreaField(label=_l("Message"), validators=[required()])
    page_id = HiddenField()
