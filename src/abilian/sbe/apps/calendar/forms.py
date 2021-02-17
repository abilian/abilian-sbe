import bleach
from wtforms import StringField, TextAreaField, ValidationError
from wtforms.fields.html5 import URLField

from abilian.i18n import _l
from abilian.web.forms import Form
from abilian.web.forms.fields import DateTimeField
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import required
from abilian.web.forms.widgets import RichTextWidget

ALLOWED_TAGS = [
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
]

ALLOWED_ATTRIBUTES = {
    "*": ["title"],
    "p": ["style"],
    "a": ["href", "title"],
    "abbr": ["title"],
    "acronym": ["title"],
    "img": ["src", "alt", "title"],
}

ALLOWED_STYLES = ["text-align"]

WIDGET_ALLOWED = {}
for attr in ALLOWED_TAGS:
    allowed = ALLOWED_ATTRIBUTES.get(attr, True)
    if not isinstance(allowed, bool):
        allowed = {tag: True for tag in allowed}
    WIDGET_ALLOWED[attr] = allowed


class EventForm(Form):
    title = StringField(label=_l("Title"), filters=(strip,), validators=[required()])

    start = DateTimeField(_l("Start"), validators=[required()])
    end = DateTimeField(_l("End"), validators=[required()])

    location = TextAreaField(label=_l("Location"), filters=(strip,))

    url = URLField(label=_l("URL"), filters=(strip,))

    description = TextAreaField(
        label=_l("Description"),
        widget=RichTextWidget(allowed_tags=WIDGET_ALLOWED),
        filters=(strip,),
        validators=[required()],
    )

    def validate_description(self, field):
        field.data = bleach.clean(
            field.data,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            styles=ALLOWED_STYLES,
            strip=True,
        )

    def validate_end(self, field):
        if self.start.data > self.end.data:
            raise ValidationError(_l("End date/time must be after start"))


EventForm.start.kwargs["raw_data"] = [" | 09:00"]
EventForm.end.kwargs["raw_data"] = [" | 18:00"]
