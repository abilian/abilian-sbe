# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from datetime import timedelta

from flask import current_app, flash, redirect, render_template, request, url_for
from jinja2 import Template

from abilian.core.extensions import db
from abilian.i18n import _, _l
from abilian.services import get_service
from abilian.web import csrf
from abilian.web.admin import AdminPanel


class Key:
    template = Template(
        '<input type="text" class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm" '
        'id="{{ key.id }}" name="{{ key.id }}" value="{{ config[key.id] }}" />'
    )

    def __init__(
        self,
        id: str,
        type_: str,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        self.id = id
        self.type = type_
        self.label = label
        self.description = description

    def __html__(self) -> str:
        return render_template(self.template, key=self, config=current_app.config)

    def value_from_request(self):
        return request.form.get(self.id).strip()


class SessionLifeTimeKey(Key):
    template = "admin/settings_session_lifetime.html"

    def __init__(self) -> None:
        super().__init__(
            "PERMANENT_SESSION_LIFETIME",
            "timedelta",
            label=_l("Session lifetime"),
            description=_l(
                "Session expiration time after last visit. "
                "When session is expired user must login again."
            ),
        )

    def value_from_request(self):
        form = request.form
        days = max(0, int(form.get(f"{self.id}:days") or 0))
        hours = min(23, max(0, int(form.get(f"{self.id}:hours") or 0)))
        minutes = min(59, max(0, int(form.get(f"{self.id}:minutes") or 0)))

        if (days + hours) == 0 and minutes < 10:
            # avoid dummy sessions durations: minimum is 10 minutes
            msg = _("Minimum session lifetime is 10 minutes. Value has been adjusted.")
            flash(msg, "warning")
            minutes = 10

        return timedelta(days=days, hours=hours, minutes=minutes)

    def _get_current(self, field: str) -> int:
        td = current_app.config.get(self.id)
        if td:
            match field:
                case "days":
                    return td.days
                case "hours":
                    return int(td.seconds / 3600)
                case "minutes":
                    return int(td.seconds % 3600 / 60)
        return 0

    @property
    def days(self) -> int:
        return self._get_current("days")

    @property
    def hours(self) -> int:
        return self._get_current("hours")

    @property
    def minutes(self) -> int:
        return self._get_current("minutes")


# FIXME: the settings panel should offer hooks for external modules and thus
# provide unified interface for site settings / customization


class SettingsPanel(AdminPanel):
    id = "settings"
    label = _l("Settings")
    icon = "cog"

    # FIXME: this is very basic, and we support only "string" at this time.
    # A form shoud be used. Really.
    _keys = (
        Key("SITE_NAME", "string", _l("Site name")),
        Key("MAIL_SENDER", "string", _l("Mail sender")),
        SessionLifeTimeKey(),
    )

    @property
    def settings(self):
        return get_service("settings").namespace("config")

    def get(self) -> str:
        return render_template("admin/settings.html", keys=self._keys)

    @csrf.protect
    def post(self):
        action = request.form.get("action")

        if action == "save":
            settings = self.settings
            for key in self._keys:
                value = key.value_from_request()
                settings.set(key.id, value, key.type)

            db.session.commit()

            # FIXME: this is weak: only this process will have its config changed;
            # full reload of app stack (web workers + task workers) has to be done
            # manually.
            current_app.config.update(settings.as_dict())
            flash(_("Changes saved."))

        return redirect(url_for(".settings"))
