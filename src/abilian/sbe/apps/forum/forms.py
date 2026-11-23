# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from wtforms import BooleanField, StringField, TextAreaField

from abilian.i18n import _l
from abilian.web.forms import Form, RichTextWidget
from abilian.web.forms.fields import FileField
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import Length, optional, required
from abilian.web.rich_text import (
    ALLOWED_ATTRIBUTES,
    ALLOWED_STYLES,
    ALLOWED_TAGS,
    sanitize_html,
)

# TODO: drop this re-export once `forum/tasks.py` calls `sanitize_html` instead.
__all__ = [
    "ALLOWED_ATTRIBUTES",
    "ALLOWED_STYLES",
    "ALLOWED_TAGS",
    "BasePostForm",
    "PostEditForm",
    "PostForm",
    "ThreadForm",
]

# instantiate this one before PostForm fields, so that it is listed first
# when Threadform is displayed
_TITLE_FIELD = StringField(
    label=_l("Title"), filters=(strip,), validators=[required(), Length(max=150)]
)


class BasePostForm(Form):
    message = TextAreaField(
        label=_l("Message"),
        widget=RichTextWidget(),
        filters=(strip,),
        validators=[required()],
    )
    attachments = FileField(
        label=_l("Attachments"), multiple=True, validators=[optional()]
    )

    def validate_message(self, field) -> None:
        field.data = sanitize_html(field.data)


class PostForm(BasePostForm):
    send_by_email = BooleanField(label=_l("Send by email?"), default=True)


class ThreadForm(PostForm):
    title = _TITLE_FIELD


class PostEditForm(BasePostForm):
    reason = StringField(
        label=_l("Reason"),
        description=_l("Description of your edit"),
        filters=(strip,),
        validators=(optional(),),
    )
