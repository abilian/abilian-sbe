# Copyright (c) 2012-2024, Abilian SAS

"""The site's settings, saved in the database: each process reads them as it starts
(`abilian.setup.load_stored_settings`)."""

from __future__ import annotations

import re
from datetime import timedelta

from flask import current_app, flash, redirect, render_template, request, url_for
from jinja2 import Template
from werkzeug.exceptions import BadRequest

from abilian.core.dramatiq.scheduler import DEFAULT_SCHEDULE
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
        return request.form[self.id].strip()


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


#: The daily digest's schedule, in the scheduler's configuration.
DIGEST_SCHEDULE = "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST"

#: A schedule that runs once a day, on the hour: the hour.
DAILY_AT = re.compile(r"^0 (\d{1,2}) \* \* \*$")


def digest_hour(config: dict) -> int | None:
    """The hour the daily digest leaves at, on the server's clock; None for a
    schedule set otherwise in the configuration files."""
    schedule = config.get(DIGEST_SCHEDULE) or DEFAULT_SCHEDULE[DIGEST_SCHEDULE]
    match = DAILY_AT.match(schedule.strip())
    return int(match.group(1)) if match else None


class DigestHourKey(Key):
    """The daily digest's hour, kept as the schedule the scheduler reads."""

    def __init__(self) -> None:
        super().__init__(
            DIGEST_SCHEDULE,
            "string",
            label=_l("Daily digest"),
            description=_l(
                "The hour it leaves, on the server's clock. The task scheduler "
                "takes it up when it restarts."
            ),
        )

    @property
    def hour(self) -> int | None:
        return digest_hour(current_app.config)

    def value_from_request(self) -> str:
        value = request.form[self.id]
        if not value:
            # A schedule set in the configuration files, kept as it is.
            return current_app.config.get(self.id) or DEFAULT_SCHEDULE[self.id]
        if not value.isdigit() or int(value) > 23:
            raise BadRequest
        return f"0 {int(value)} * * *"


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
        DigestHourKey(),
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
