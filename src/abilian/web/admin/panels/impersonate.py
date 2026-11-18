# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import abort, redirect, request, url_for
from flask_login import login_user

from abilian.core.models.subjects import User
from abilian.web import csrf
from abilian.web.admin.panel import AdminPanel

if TYPE_CHECKING:
    from werkzeug.wrappers import Response


class ImpersonatePanel(AdminPanel):
    id = "impersonate"
    label = "Impersonate"
    icon = "user"

    def get(self):
        user_email = request.args.get("email")
        if not user_email:
            return "UI not done yet. Add '?email=...' at the end of this URL for now."

        user = User.query.filter(User.email == user_email).one()
        login_user(user)
        return redirect(url_for("main.home"))

    @csrf.protect
    def post(self) -> Response:
        """Sign in as someone, to see what they see: an account's page asks for it."""
        user = User.query.get(request.form.get("user", type=int))
        if user is None:
            abort(404)
        login_user(user)
        return redirect(url_for("main.home"))
