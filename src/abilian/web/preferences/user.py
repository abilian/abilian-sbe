# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import babel.dates
from flask import request
from wtforms import StringField
from wtforms.validators import ValidationError

from abilian.i18n import _, _l, get_default_locale
from abilian.web.forms import Form, fields, required, widgets
from abilian.web.forms.validators import open_png_or_jpeg

if TYPE_CHECKING:
    from abilian.web.forms.fields import FileField


class UserPreferencesForm(Form):
    password = StringField(
        _l("New Password"), widget=widgets.PasswordInput(autocomplete="off")
    )
    confirm_password = StringField(
        _l("Confirm new password"), widget=widgets.PasswordInput(autocomplete="off")
    )

    photo = fields.FileField(
        label=_l("Photo"), widget=widgets.ImageInput(width=55, height=55)
    )

    locale = fields.LocaleSelectField(
        label=_l("Preferred Language"),
        validators=[required()],
        default=get_default_locale,
    )

    timezone = fields.TimezoneField(
        label=_l("Time zone"), validators=(required(),), default=babel.dates.LOCALTZ
    )

    def validate_password(self, field: StringField) -> None:
        pwd = field.data
        confirmed = self["confirm_password"].data

        if pwd != confirmed:
            raise ValidationError(
                _(
                    "Passwords differ. Ensure you have typed same password "
                    'in both "password" field and "confirm password" field.'
                )
            )

    def validate_photo(self, field: FileField) -> None:
        data = request.form.get(field.name)
        if not data:
            return

        im = open_png_or_jpeg(field.data)

        # convert to jpeg
        # FIXME: better do this at model level?
        jpeg = BytesIO()
        im.convert("RGB").save(jpeg, "JPEG")
        field.data = jpeg.getvalue()
