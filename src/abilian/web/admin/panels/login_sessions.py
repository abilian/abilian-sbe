# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from flask import render_template

from abilian.i18n import _
from abilian.services.auth.models import LoginSession
from abilian.web.admin import AdminPanel

from .geoip.ip_country_code import ip_to_country_code


class LoginSessionsPanel(AdminPanel):
    id = "login_sessions"
    label = "Session log"
    icon = "sign-in"

    def get(self) -> str:
        sessions = LoginSession.query.order_by(LoginSession.id.desc()).limit(50).all()
        unknown_country = _("Country unknown")

        for session in sessions:
            if session.ip_address:
                # if several IPs, only use last IP in the list, most likely the
                # public address
                ip_address = session.ip_address.rpartition(",")[-1]
                session.country = ip_to_country_code(ip_address) or unknown_country

        ctx = {"sessions": sessions}
        return render_template("admin/login_sessions.html", **ctx)
