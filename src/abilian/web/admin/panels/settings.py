# Copyright (c) 2012-2024, Abilian SAS

"""The site's settings, saved in the database: each process reads them as it starts
(`abilian.setup.load_stored_settings`)."""

from __future__ import annotations

import re

from flask import current_app, flash, redirect, render_template, request, url_for
from jinja2 import Template
from werkzeug.exceptions import BadRequest

from abilian.core.dramatiq.scheduler import DEFAULT_SCHEDULE
from abilian.core.extensions import db
from abilian.i18n import _, _l
from abilian.services import get_service
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


#: The daily digest's schedule, in the scheduler's configuration.
DIGEST_SCHEDULE = "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST"

#: What the settings' form sends for a digest that is not sent.
OFF = "off"

#: A schedule that runs once a day, on the hour: the hour.
DAILY_AT = re.compile(r"^0 (\d{1,2}) \* \* \*$")


def digest_schedule(config: dict) -> str:
    """The daily digest's schedule as the scheduler reads it: "" when it is not
    sent at all (`crontab_from_config`)."""
    return config.get(DIGEST_SCHEDULE, DEFAULT_SCHEDULE[DIGEST_SCHEDULE]).strip()


def digest_hour(config: dict) -> int | None:
    """The hour the daily digest leaves at, on the server's clock; None when it is
    not sent, or sent on a schedule set otherwise in the configuration files."""
    match = DAILY_AT.match(digest_schedule(config))
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

    @property
    def schedule(self) -> str:
        return digest_schedule(current_app.config)

    def value_from_request(self) -> str:
        value = request.form[self.id]
        if value == OFF:
            return ""
        if not value:
            # A schedule set in the configuration files, kept as it is.
            return self.schedule
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
    )

    @property
    def settings(self):
        return get_service("settings").namespace("config")

    def get(self) -> str:
        return render_template("admin/settings.html", keys=self._keys)

    def post(self):
        action = request.form.get("action")

        if action == "save":
            settings = self.settings
            for key in self._keys:
                value = key.value_from_request()
                settings.set(key.id, value, key.type)

            db.session.commit()

            # This process at once; the others (web workers, the task scheduler)
            # read the saved settings as they start, so they need a restart.
            current_app.config.update(settings.as_dict())
            flash(_("Changes saved."))

        return redirect(url_for(".settings"))
