# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import babel.dates
from flask import current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import InternalServerError
from wtforms import StringField
from wtforms.validators import ValidationError

from abilian.core.extensions import db
from abilian.i18n import _, _l, get_default_locale
from abilian.services.preferences.panel import PreferencePanel
from abilian.web import csrf
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


class UserPreferencesPanel(PreferencePanel):
    id = "user"
    label = _l("About me")

    def is_accessible(self) -> bool:
        return True

    def get(self):
        # Manual security check, should be done by the framework instead.
        if not self.is_accessible():
            raise InternalServerError

        data = {}
        photo = g.user.photo
        if photo:
            # subclass str/bytes to set additional 'url' attribute

            photo = type(
                "Photo",
                (bytes,),
                {"object": photo, "url": url_for("users.photo", user_id=g.user.id)},
            )
            data["photo"] = photo

        form = UserPreferencesForm(obj=g.user, formdata=None, prefix=self.id, **data)
        if form["locale"].data is None:
            form["locale"].data = get_default_locale()

        ctx = {"form": form, "title": self.label}
        return render_template("preferences/user.html", **ctx)

    @csrf.support_graceful_failure
    def post(self):
        # Manual security check, should be done by the framework instead.
        if not self.is_accessible():
            raise InternalServerError

        if request.form["_action"] == "cancel":
            return redirect(url_for(".user"))

        form = UserPreferencesForm(request.form, prefix=self.id)

        if form.validate():
            if csrf.has_failed():
                current_app.extensions["csrf-handler"].flash_csrf_failed_message()
                return render_template("preferences/user.html", form=form)

            del form.confirm_password
            if form.password.data:
                g.user.set_password(form.password.data)
                flash(_("Password changed"), "success")
            del form.password

            form.populate_obj(g.user)

            db.session.commit()
            flash(_("Preferences saved."), "info")
            return redirect(url_for(".user"))
        return render_template("preferences/user.html", form=form)
