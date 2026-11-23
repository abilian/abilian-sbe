# Copyright (c) 2026, Abilian SAS

"""One's account on one page: one's photo, name, job title and organization, the
language and time zone the site speaks in, the daily digest, the password. It takes
the place of Abilian Core's "About me" panel and of the notifications panel; the
address, which one signs in with, is not changed here."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import flash, redirect, render_template, request, url_for
from wtforms import BooleanField, StringField
from wtforms.validators import Length, ValidationError

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated_user
from abilian.core.models.subjects import AFFILIATION_LENGTH
from abilian.i18n import _, _l, get_default_locale
from abilian.services import get_service
from abilian.services.auth.passwords import weakness
from abilian.services.preferences.panel import PreferencePanel
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import required
from abilian.web.preferences.user import UserPreferencesForm

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

    from abilian.core.models.subjects import User
    from abilian.services.preferences.service import PreferenceService

#: Where the daily digest's choice is kept, among a person's preferences.
DAILY = "sbe:notifications:daily"


class AccountForm(UserPreferencesForm):
    first_name = StringField(
        _l("First name"), filters=(strip,), validators=[required()]
    )
    last_name = StringField(_l("Last name"), filters=(strip,), validators=[required()])
    job_title = StringField(
        _l("Job title"), filters=(strip,), validators=[Length(max=AFFILIATION_LENGTH)]
    )
    organization = StringField(
        _l("Organization"),
        filters=(strip,),
        validators=[Length(max=AFFILIATION_LENGTH)],
    )
    daily = BooleanField(_l("Each morning, what happened in my communities"))

    def validate_password(self, field: StringField) -> None:
        """The rules of a new password, and the same one twice; none keeps it."""
        if not field.data:
            return
        problem = weakness(field.data)
        if problem:
            raise ValidationError(problem)
        super().validate_password(field)


class AccountPanel(PreferencePanel):
    """`preferences.user`, where the account menu and the digest's e-mails lead."""

    id = "user"
    label = _l("My account")

    def get(self) -> str:
        user = authenticated_user()
        form = AccountForm(
            obj=user,
            formdata=None,
            daily=_preferences().get_preferences(user).get(DAILY, False),
        )
        if form.locale.data is None:
            form.locale.data = get_default_locale()
        return _render(form, user)

    def post(self) -> Response | str:
        user = authenticated_user()
        form = AccountForm(request.form)
        if not form.validate():
            return _render(form, user)

        if form.password.data:
            user.set_password(form.password.data)
            flash(_("Password changed"), "success")
        _preferences().set_preferences(user, **{DAILY: form.daily.data})
        for name in ("password", "confirm_password", "daily"):
            del form[name]
        form.populate_obj(user)
        db.session.commit()
        flash(_("Preferences saved."), "info")
        return redirect(url_for(".user"))


def _preferences() -> PreferenceService:
    return cast("PreferenceService", get_service("preferences"))


def _render(form: AccountForm, user: User) -> str:
    return render_template("preferences/account.html", form=form, user=user)
