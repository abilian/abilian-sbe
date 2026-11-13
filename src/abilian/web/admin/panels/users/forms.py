# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import sqlalchemy as sa
from wtforms import BooleanField, StringField
from wtforms.validators import ValidationError

from abilian.core.models.subjects import Group
from abilian.i18n import _, _l
from abilian.services.security.models import Role
from abilian.web.forms import Form, widgets
from abilian.web.forms.fields import MultipleChoiceField, QuerySelectField
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import optional, required


class BaseUserAdminForm(Form):
    email = StringField(
        _l("Email"),
        description=_l("Users log in with their email address."),
        view_widget=widgets.EmailWidget(),
        filters=(strip,),
        validators=[required()],
    )
    first_name = StringField(
        _l("First Name"),
        description=_l("ex: John"),
        filters=(strip,),
        validators=[required()],
    )
    last_name = StringField(
        _l("Last Name"),
        description=_l("ex: Smith"),
        filters=(strip,),
        validators=[required()],
    )

    can_login = BooleanField(
        _l("Login enabled"),
        description=_l("If unchecked, user will not be able to connect."),
        widget=widgets.BooleanWidget(),
    )

    groups = QuerySelectField(
        _l("Groups"),
        validators=(optional(),),
        multiple=True,
        collection_class=set,
        query_factory=lambda: Group.query.order_by(sa.sql.func.lower(Group.name).asc()),
        get_label="name",
    )

    roles = MultipleChoiceField(
        _l("Roles"),
        description=_l(
            "Prefer groups to manage access rights. Directly assigning roles "
            "to users is possible but discouraged."
        ),
        choices=lambda: [(r.name, r.label) for r in Role.assignable_roles()],
    )

    password = StringField(
        _l("New Password"),
        description=_l("If empty the current password will not be changed."),
        widget=widgets.PasswordInput(autocomplete="off"),
    )


class UserAdminForm(BaseUserAdminForm):
    confirm_password = StringField(
        _l("Confirm new password"), widget=widgets.PasswordInput(autocomplete="off")
    )

    def validate_password(self, field) -> None:
        pwd = field.data
        confirmed = self["confirm_password"].data

        if pwd != confirmed:
            raise ValidationError(
                _(
                    "Passwords differ. Ensure you have typed same password in both"
                    ' "password" field and "confirm password" field.'
                )
            )


class UserCreateForm(BaseUserAdminForm):
    password = StringField(
        _l("Password"),
        description=_l("If empty a random password will be generated."),
        widget=widgets.PasswordInput(autocomplete="off"),
    )
