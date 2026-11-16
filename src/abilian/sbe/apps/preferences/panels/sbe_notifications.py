# Copyright (c) 2012-2024, Abilian SAS

"""This panel manages user setting for email reminders related to the SBE
(social netowking) app."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import flash, redirect, render_template, request, url_for
from werkzeug.exceptions import Forbidden
from wtforms import BooleanField

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated_user
from abilian.i18n import _, _l
from abilian.services import get_service
from abilian.services.preferences.panel import PreferencePanel
from abilian.web import csrf
from abilian.web.forms import Form, widgets

if TYPE_CHECKING:
    from abilian.services.preferences.service import PreferenceService


class SbeNotificationsForm(Form):
    daily = BooleanField(
        label=_("Receive by email a daily digest of activities in your communities"),
        widget=widgets.BooleanWidget(),
    )


class SbeNotificationsPanel(PreferencePanel):
    id = "sbe_notifications"
    label = _l("Community notifications")

    def is_accessible(self) -> bool:
        return True

    def get(self) -> str:
        # Manual security check, should be done by the framework instead.
        if not self.is_accessible():
            raise Forbidden

        preferences = cast("PreferenceService", get_service("preferences"))
        # preferences = app.services["preferences"]
        data = {}
        prefs = preferences.get_preferences(authenticated_user())

        for k, v in prefs.items():
            if k.startswith("sbe:notifications:"):
                data[k[18:]] = v

        form = SbeNotificationsForm(formdata=None, prefix=self.id, **data)
        return render_template("preferences/sbe_notifications.html", form=form)

    @csrf.protect
    def post(self):
        # Manual security check, should be done by the framework instead.
        if not self.is_accessible():
            raise Forbidden

        if request.form["_action"] == "cancel":
            return redirect(url_for(".sbe_notifications"))
        form = SbeNotificationsForm(request.form, prefix=self.id)
        if form.validate():
            preferences = get_service("preferences")
            for field_name, field in form._fields.items():
                if field is form.csrf_token:
                    continue
                key = f"sbe:notifications:{field_name}"
                value = field.data
                preferences.set_preferences(authenticated_user(), **{key: value})

            db.session.commit()
            flash(_("Preferences saved."), "info")
            return redirect(url_for(".sbe_notifications"))
        return render_template("preferences/sbe_notifications.html", form=form)
