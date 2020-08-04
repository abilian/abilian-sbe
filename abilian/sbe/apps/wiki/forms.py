"""Forms for the Wiki module."""
from typing import Any, Optional

from wtforms import HiddenField, StringField, TextAreaField, ValidationError
from wtforms.validators import data_required

from abilian.i18n import _, _l
from abilian.web.forms import Form
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import flaghidden
from abilian.web.forms.widgets import TextArea

from .util import page_exists


def clean_up(src: str) -> str:
    """Form filter."""
    src = src.replace("\r", "")
    return src


def int_or_none(val: Any) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


class WikiPageForm(Form):
    title = StringField(
        label=_l("Title"), filters=(strip,), validators=[data_required()]
    )
    body_src = TextAreaField(
        label=_l("Body"),
        filters=(strip, clean_up),
        validators=[data_required()],
        widget=TextArea(rows=10, resizeable="vertical"),
    )

    message = StringField(label=_l("Commit message"))
    page_id = HiddenField(filters=(int_or_none,), validators=[flaghidden()])
    last_revision_id = HiddenField(filters=(int_or_none,), validators=[flaghidden()])

    def validate_title(self, field: StringField) -> None:
        title = field.data
        if title != field.object_data and page_exists(title):
            raise ValidationError(
                _("A page with this name already exists. Please use another name.")
            )

    def validate_last_revision_id(self, field: HiddenField) -> None:
        val = field.data
        current = field.object_data

        if val is None or current is None:
            return

        if val != current:
            raise ValidationError(_("this page has been edited since"))


# Not used yet
class CommentForm(Form):
    message = TextAreaField(label=_l("Message"), validators=[data_required()])
    page_id = HiddenField()
