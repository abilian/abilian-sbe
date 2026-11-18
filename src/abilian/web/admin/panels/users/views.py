# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import Any

from flask import render_template_string, request
from werkzeug.datastructures import MultiDict

from abilian.core.extensions.login import authenticated_user
from abilian.core.models.subjects import User, gen_random_password
from abilian.services import get_service
from abilian.services.auth.models import LoginSession
from abilian.services.security.models import ADMIN, Role
from abilian.web.nav import BreadcrumbItem
from abilian.web.util import url_for
from abilian.web.views import object as views

from .forms import UserAdminForm, UserCreateForm

MUGSHOT_SIZE = 45

#: How many of an account's sign-ins its page shows.
LAST_SESSIONS = 5


# User edit / create views
class UserBase:
    Model = User
    pk = "user_id"
    base_template = "admin/_base.html"
    template = "admin/user_edit.html"

    def index_url(self):
        return url_for(".users")

    def view_url(self):
        return self.index_url()


class UserEdit(UserBase, views.ObjectEdit[User, UserAdminForm]):
    Form = UserAdminForm

    def breadcrumb(self):
        label = render_template_string("<em>{{ u.email }}</em>", u=self.obj)
        return BreadcrumbItem(label=label, url="", description=self.obj.name)

    @property
    def template_kwargs(self) -> dict[str, Any]:
        """The account's last sign-ins, beside its form."""
        kw = super().template_kwargs
        kw["sessions"] = (
            LoginSession.query.filter(LoginSession.user_id == self.obj.id)
            .order_by(LoginSession.started_at.desc())
            .limit(LAST_SESSIONS)
            .all()
        )
        return kw

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        security = get_service("security")
        roles = security.get_roles(self.obj, no_group_roles=True)
        kw["roles"] = [r.name for r in roles if r.assignable]
        return kw

    def validate(self) -> bool:
        if not super().validate():
            return False

        if authenticated_user() == self.obj:
            # self edit: don't let user shoot themself in the foot
            self.form.can_login.data = True
            roles = self.form.roles
            if ADMIN.name not in roles.data:
                roles.data.append(ADMIN.name)
        return True

    def form_valid(self, *args, **kwargs):
        del self.form.confirm_password
        if self.form.password.data:
            self.obj.set_password(self.form.password.data)
        del self.form.password

        return super().form_valid()

    def after_populate_obj(self):
        security = get_service("security")
        current_roles = security.get_roles(self.obj, no_group_roles=True)
        current_roles = {r for r in current_roles if r.assignable}
        new_roles = {Role(r) for r in self.form.roles.data}

        for r in current_roles - new_roles:
            security.ungrant_role(self.obj, r)

        for r in new_roles - current_roles:
            security.grant_role(self.obj, r)

        return super().after_populate_obj()


class UserCreate(UserBase, views.ObjectCreate[User, UserCreateForm]):
    Form = UserCreateForm
    chain_create_allowed = True

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()

        if request.method == "GET":
            # ensure formdata is not ImmutableMultiDict (request.args)
            data = MultiDict(kw.setdefault("formdata", {}))
            kw["formdata"] = data
            data["can_login"] = True

        return kw

    def form_valid(self, redirect_to=None):
        if not self.form.password.data:
            self.form.password.data = gen_random_password()

        self.obj.set_password(self.form.password.data)
        del self.form.password
        return super().form_valid()
