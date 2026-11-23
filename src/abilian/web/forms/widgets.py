# Copyright (c) 2012-2024, Abilian SAS

"""Reusable widgets to be included in views.

NOTE: code is currently quite messy. Needs to be refactored.
"""

from __future__ import annotations

import base64
import html
from typing import Any

import wtforms
from flask import current_app, render_template, render_template_string
from flask_babel import format_date, format_datetime, format_number
from markupsafe import Markup
from wtforms import IntegerField, StringField
from wtforms.widgets import (
    DateInput as BaseDateInput,
    PasswordInput as BasePasswordInput,
    Select,
    TextArea as BaseTextArea,
    html_params,
)

from abilian.core.extensions.login import authenticated_user
from abilian.core.models.blob import Blob
from abilian.i18n import _, _l
from abilian.services import image
from abilian.services.image import get_format
from abilian.web import url_for

__all__ = [
    # Widgets
    "BooleanWidget",
    "DateInput",
    "DateTimeInput",
    "DateTimeWidget",
    "DateWidget",
    "DefaultViewWidget",
    "EmailWidget",
    "EntityWidget",
    "FileInput",
    "FloatWidget",
    "ImageInput",
    "ListWidget",
    "MoneyWidget",
    "RichTextWidget",
    "SelectWidget",
    "TextArea",
]


#
# Single object view
#
#
# Used to describe single entity views.
#
# Form field widgets #####################################################
class TextInput(wtforms.widgets.TextInput):
    """Support pre and post icons.

    An Icon can be a plain string, or an instance of
    :class:`abilian.web.action.Icon`.
    """

    pre_icon: str | None = None
    post_icon: str | None = None

    def __init__(
        self,
        input_type: Any | None = None,
        pre_icon: Any | None = None,
        post_icon: Any | None = None,
    ) -> None:
        super().__init__(input_type)

        if pre_icon is not None:
            self.pre_icon = pre_icon
        if post_icon is not None:
            self.post_icon = post_icon

    def __call__(self, field, **kwargs):
        if not any((self.pre_icon, self.post_icon)):
            return super().__call__(field, **kwargs)

        kwargs.setdefault("type", self.input_type)
        if "value" not in kwargs:
            kwargs["value"] = field._value()

        params = self.html_params(name=field.name, **kwargs)
        return Markup(
            render_template_string(
                """
                <div class="flex rounded-md shadow-sm input-group-type-{{ widget.typename }}">
                {%- if widget.pre_icon %}
                  <span class="inline-flex items-center px-3 rounded-l-md border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">{{ widget.pre_icon }}</span>
                {%- endif %}
                  <input {{ params | safe}} class="flex-1 block w-full px-3 py-2 border border-gray-300 {% if widget.pre_icon %}rounded-r-md{% elif widget.post_icon %}rounded-l-md{% else %}rounded-md{% endif %} focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
                {%- if widget.post_icon %}
                  <span class="inline-flex items-center px-3 rounded-r-md border border-l-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">{{ widget.post_icon }}</span>
                {%- endif %}
                </div>
                """,
                widget=self,
                params=params,
            )
        )

    @property
    def typename(self):
        return self.__class__.__name__.lower()


class TextArea(BaseTextArea):
    """Accepts "resizeable" parameter: "vertical", "horizontal", "both",
    None."""

    _resizeable_valid = ("vertical", "horizontal", "both", None)
    resizeable = None
    rows = None

    def __init__(
        self,
        resizeable: str | None = None,
        rows: int | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        if resizeable not in self._resizeable_valid:
            msg = (
                f"Invalid value for resizeable: {resizeable}, "
                f"valid values are: {self._resizeable_valid!r}"
            )
            raise ValueError(msg)
        if resizeable:
            self.resizeable = f"resizeable-{resizeable}"
        else:
            self.resizeable = "not-resizeable"

        if rows:
            self.rows = int(rows)

    def __call__(self, *args, **kwargs):
        if self.resizeable:
            css = kwargs.get("class_", "")
            kwargs["class_"] = f"{css} {self.resizeable}"

        if self.rows and "rows" not in kwargs:
            kwargs["rows"] = self.rows

        return super().__call__(*args, **kwargs)


class FileInput:
    """Renders a file input.

    Inspired from http://www.abeautifulsite.net/blog/2013/08/whipping-
    file-inputs-into-shape-with-bootstrap-3/
    """

    def __init__(self, template: str = "widgets/file_input.html") -> None:
        self.template = template

    def __call__(self, field, **kwargs):
        kwargs.setdefault("id", field.id)
        kwargs["name"] = field.name
        kwargs["type"] = "file"
        kwargs["disabled"] = "disabled"  # JS widget will activate it
        input_elem = f"<input {html_params(**kwargs)}>"
        button_label = _("Add file") if "multiple" in kwargs else _("Select file")

        existing = self.build_exisiting_files_list(field)
        uploads = self.build_uploads_list(field)

        if not field.multiple and uploads:
            # single file field: exising file replaced by new upload, don't show
            # existing
            existing = []
        else:
            for data in existing:
                # this might be a very big bytes object: in any case it will not be used
                # in widget's template, and during development it makes very large pages
                # due to debugtoolbar capturing template parameters
                del data["file"]

        ctx = {
            "id": field.id,
            "field": field,
            "widget": self,
            "input": input_elem,
            "button_label": button_label,
            "existing": existing,
            "uploaded": uploads,
        }
        return Markup(render_template(self.template, **ctx))

    def build_exisiting_files_list(self, field):
        existing = []
        blob = None
        object_data = field.object_data

        if not object_data:
            return existing

        if not field.multiple:
            object_data = [object_data]
            blob = field.blob

        for idx, data in enumerate(object_data):
            if data is not None:
                if hasattr(data, "content_length"):
                    size = data.content_length
                else:
                    try:
                        size = len(bytes(data))
                    except Exception:
                        # FIXME: when does it happen ?
                        size = 0
                existing.append(
                    {
                        "file": data,
                        "size": size,
                        "delete": idx in field.delete_files_index,
                    }
                )
                if hasattr(data, "filename"):
                    existing[-1]["filename"] = data.filename
                elif blob and isinstance(blob, Blob):
                    existing[-1]["filename"] = blob.meta.get("filename", "")

        return existing

    def build_uploads_list(self, field):
        uploads = current_app.extensions["uploads"]
        # Uploads belong to a logged-in user: the uploads blueprint requires one.
        user = authenticated_user()
        uploaded = []

        for handle in field.upload_handles:
            file_ = uploads.get_file(user, handle)
            if file_ is None:
                continue
            meta = uploads.get_metadata(user, handle)
            uploaded.append(
                {
                    "file": file_,
                    "handle": handle,
                    "filename": meta.get("filename", handle),
                    "size": file_.stat().st_size,
                }
            )

        return uploaded


class ImageInput(FileInput):
    """An image widget with client-side preview.

    To show current image field data has to provide an attribute named
    `url`.
    """

    def __init__(
        self,
        template: str = "widgets/image_input.html",
        width: int = 120,
        height: int = 120,
        resize_mode: str = image.CROP,
        valid_extensions: tuple[str, str, str] = ("jpg", "jpeg", "png"),
    ) -> None:
        super().__init__(template=template)
        self.resize_mode = resize_mode
        self.valid_extensions = valid_extensions
        self.width, self.height = width, height

    def build_exisiting_files_list(self, field):
        existing = super().build_exisiting_files_list(field)
        for data in existing:
            value = data["file"]
            if value:
                if hasattr(value, "url"):
                    image_url = value.url
                else:
                    image_url = self.get_b64_thumb_url(
                        self.get_thumb(value, self.width, self.height)
                    )

                data["image_url"] = image_url

        return existing

    def build_uploads_list(self, field):
        uploaded = super().build_uploads_list(field)
        for data in uploaded:
            value = data["file"]
            if value:
                if hasattr(value, "url"):
                    image_url = value.url
                else:
                    with value.open("rb") as in_:
                        image_url = self.get_b64_thumb_url(
                            self.get_thumb(in_, self.width, self.height)
                        )

                data["image_url"] = image_url

        return uploaded

    def get_thumb(self, data, width, height):
        try:
            get_format(data)
        except OSError:
            return ""
        return image.resize(data, width, height, mode=self.resize_mode)

    def get_b64_thumb_url(self, img) -> str:
        if not img:
            return ""
        try:
            fmt = image.get_format(img).lower()
        except OSError:
            return ""
        thumb = base64.b64encode(img).decode("ascii")
        return f"data:image/{fmt};base64,{thumb}"

    def render_view(self, field, **kwargs):
        data = field.data
        if not data:
            return ""
        try:
            get_format(data)
        except OSError:
            return ""

        width = kwargs.get("width", self.width)
        height = kwargs.get("heigth", self.height)

        thumb = self.get_thumb(data, width, height)
        width, height = image.get_size(thumb)

        tmpl = '<img src="{{ url }}" width="{{ width }}" height="{{ height }}" />'
        ctx = {"url": self.get_b64_thumb_url(thumb), "width": width, "height": height}
        return render_template_string(tmpl, **ctx)


class DateInput(BaseDateInput):
    """The browser's own date input. It sends YYYY-MM-DD whatever the locale."""

    def render_view(self, field, **kwargs):
        return format_date(field.data) if field.data else ""


class DateTimeInput:
    """A native date input and a native time input, both named after the field,
    so the form sends the two halves as one list: ["2026-10-30", "09:00"].

    Two inputs rather than one datetime-local, so a form can suggest a time and
    leave the date blank.
    """

    def __call__(self, field, **kwargs):
        kwargs.setdefault("id", field.id)
        field_id = kwargs.pop("id")
        kwargs.pop("value", None)
        date_value, _sep, time_value = field._value().partition(" ")
        shared = {"name": field.name, "required": field.flags.required, **kwargs}
        date_params = html_params(type="date", id=field_id, value=date_value, **shared)
        time_params = html_params(
            type="time",
            id=f"{field_id}-time",
            value=time_value,
            aria_label=field.label.text,
            **shared,
        )
        return Markup(
            '<div class="flex flex-wrap items-center gap-2">'
            f"<input {date_params}><input {time_params}>"
            "</div>"
        )


class DefaultViewWidget:
    def render_view(self, field: IntegerField | StringField, **kwargs: Any) -> str:
        # [], None and other must be rendered using empty string
        return str(field.object_data or "")


class BooleanWidget(wtforms.widgets.CheckboxInput):
    """An ordinary checkbox.

    It used to grow an `on_off_mode` that emitted a dozen data-* attributes for
    bootstrap-switch. The plugin is gone -- unstyled it rendered the literal
    text "ON OFF" beside a bare checkbox and moved the input out of its
    <label> -- and nothing has read those attributes since.
    """

    def render_view(self, field, **kwargs) -> str:
        return "\u2713" if field.object_data else ""  # Text_type "Check mark"


class PasswordInput(BasePasswordInput):
    """Supports setting 'autocomplete' at instanciation time."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.autocomplete = kwargs.pop("autocomplete", None)
        super().__init__(*args, **kwargs)

    def __call__(self, field, **kwargs):
        kwargs.setdefault("autocomplete", self.autocomplete)
        return super().__call__(field, **kwargs)

    def render_view(self, field, **kwargs) -> str:
        return "*****"


class FloatWidget(wtforms.widgets.TextInput):
    """In view mode, format float number to 'precision' decimal."""

    def __init__(self, precision=None) -> None:
        self.precision = precision
        if precision is not None:
            self._fmt = f".{precision:d}f"

    def render_view(self, field, **kwargs):
        data = field.object_data
        if data is None:
            return ""

        return format(data, self._fmt)


class DateWidget(wtforms.widgets.TextInput):
    def render_view(self, field, **kwargs):
        return format_date(field.object_data) if field.object_data else ""


class DateTimeWidget(DateWidget):
    def render_view(self, field, **kwargs):
        return format_datetime(field.object_data) if field.object_data else ""


class EntityWidget:
    def render_view(self, field, **kwargs):
        objs = field.object_data
        if not field.multiple:
            objs = [objs]
        return ", ".join(
            f'<a href="{url_for(o)}">{html.escape(o.name)}</a>' for o in objs if o
        )


class HoursWidget(TextInput):
    """Widget used to show / enter hours.

    Currently hardcoded to heure(s)
    """

    post_icon = _l("hour(s)")
    input_type = "number"

    def render_view(self, field, **kwargs) -> str:
        val = field.object_data
        unit = "h"

        if val is None:
            return ""

        # \u00A0: non-breakable whitespace
        return f"{val}\u00a0{unit}"


class MoneyWidget(TextInput):
    """Widget used to show / enter money amount.

    Currently hardcoded to € / k€.
    """

    post_icon = "€"
    input_type = "number"

    def render_view(self, field, **kwargs) -> str:
        val = field.object_data
        unit = "€"

        if val is None:
            return ""

        if val > 1000:
            unit = "k€"
            val = round(val / 1000.0)

        # `format_currency()` is not used since it display numbers with cents
        # units, which we don't want
        #
        # \u00A0: non-breakable whitespace
        return f"{format_number(val)}\u00a0{unit}"


class EmailWidget(TextInput):
    pre_icon = "@"


class RichTextWidget:
    template = "widgets/richtext.html"

    def __call__(self, field, **kwargs):
        value = kwargs.pop("value") if "value" in kwargs else field._value()
        return render_template(self.template, field=field, value=value, kw=kwargs)


class ListWidget(wtforms.widgets.ListWidget):
    """display field label is optionnal."""

    def __init__(
        self, html_tag: str = "ul", prefix_label: bool = True, show_label: bool = True
    ) -> None:
        super().__init__(html_tag, prefix_label)
        self.show_label = show_label

    def __call__(self, field, **kwargs):
        if self.show_label:
            return super().__call__(field, **kwargs)

        kwargs.setdefault("id", field.id)
        html = [f"<{self.html_tag} {wtforms.widgets.html_params(**kwargs)}>"]
        for subfield in field:
            html.append(f"<li>{subfield()}</li>")

        html.append(f"</{self.html_tag}>")
        return Markup("".join(html))

    def render_view(self, field, **kwargs):
        data = field.data
        is_empty = data == [] if field.multiple else data is None

        if not is_empty:
            data = (
                [label for v, label, checked, *_rest in field.iter_choices() if checked]
                if (hasattr(field, "iter_choices") and callable(field.iter_choices))
                else field.object_data
            )
        else:
            data = []

        tpl = """{%- for obj in data %}
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{{ obj }}</span>
              {%- endfor %}"""
        return Markup(render_template_string(tpl, data=data))


#
# Selection widget.
#
class SelectWidget(Select):
    """The browser's own select, with a blank option and a read-only rendering."""

    def render_view(self, field, **kwargs):
        labels = [
            str(label)
            for _value, label, checked, *_rest in field.iter_choices()
            if checked
        ]
        return "; ".join(labels)

    @classmethod
    def render_option(cls, choice, **kwargs):
        if choice.value is None:
            return Markup("<option></option>")
        return super().render_option(choice, **kwargs)
