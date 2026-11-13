# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import bleach
from bleach.css_sanitizer import CSSSanitizer
from wtforms import BooleanField, StringField, TextAreaField

from abilian.i18n import _l
from abilian.web.forms import Form, RichTextWidget
from abilian.web.forms.fields import FileField
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import Length, optional, required

ALLOWED_TAGS = {
    "a",
    "abbr",
    "acronym",
    "b",
    "blockquote",
    "br",
    "code",
    "em",
    "i",
    "li",
    "ol",
    "strong",
    "ul",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "u",
    "img",
}

ALLOWED_ATTRIBUTES = {
    "*": ["title"],
    "p": ["style"],
    "a": ["href", "title"],
    "abbr": ["title"],
    "acronym": ["title"],
    "img": ["src", "alt", "title"],
}

ALLOWED_STYLES = ["text-align"]

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
        css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)
        field.data = bleach.clean(
            field.data,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            css_sanitizer=css_sanitizer,
            strip=True,
        )


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
