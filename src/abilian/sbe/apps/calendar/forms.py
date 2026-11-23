# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from wtforms import StringField, TextAreaField, URLField
from wtforms.validators import ValidationError

from abilian.i18n import _l
from abilian.web.forms import Form
from abilian.web.forms.fields import DateTimeField
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import required
from abilian.web.forms.widgets import RichTextWidget
from abilian.web.rich_text import sanitize_html


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
        field.data = sanitize_html(field.data)

    def validate_end(self, field) -> None:
        if self.start.data > self.end.data:
            raise ValidationError(_l("End date/time must be after start"))
