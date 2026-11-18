# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import bleach
from bleach.css_sanitizer import CSSSanitizer
from wtforms import StringField, TextAreaField, URLField
from wtforms.validators import ValidationError

from abilian.i18n import _l
from abilian.web.forms import Form
from abilian.web.forms.fields import DateTimeField
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import required
from abilian.web.forms.widgets import RichTextWidget

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


class EventForm(Form):
    title = StringField(label=_l("Title"), filters=(strip,), validators=[required()])

    start = DateTimeField(_l("Start"), validators=[required()])
    end = DateTimeField(_l("End"), validators=[required()])

    location = TextAreaField(label=_l("Location"), filters=(strip,))

    url = URLField(label=_l("URL"), filters=(strip,))

    description = TextAreaField(
        label=_l("Description"),
        widget=RichTextWidget(),
        filters=(strip,),
        validators=[required()],
    )

    def validate_description(self, field) -> None:
        css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)
        field.data = bleach.clean(
            field.data,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            css_sanitizer=css_sanitizer,
            strip=True,
        )

    def validate_end(self, field) -> None:
        if self.start.data > self.end.data:
            raise ValidationError(_l("End date/time must be after start"))
