# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from wtforms import StringField, TextAreaField
from wtforms_alchemy import model_form_factory

from abilian.i18n import _l
from abilian.sbe.apps.communities.models import Community
from abilian.web.forms import Form, widgets as abilian_widgets
from abilian.web.forms.fields import QuerySelectField
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import optional, required

ModelForm: type[Form] = model_form_factory(Form)


class UserProfileForm(ModelForm):
    pass


class UserProfileViewForm(UserProfileForm):
    communautes = QuerySelectField(
        "Communautés d'appartenance",
        get_label="name",
        view_widget=abilian_widgets.ListWidget(),
        # `Community.query` needs an app context, so it cannot be bound at import time.
        query_factory=lambda: Community.query.all(),  # noqa: PLW0108
        multiple=True,
        validators=[optional()],
    )


class GroupForm(Form):
    name = StringField(
        _l("Name"),
        filters=(strip,),
        validators=[required(message=_l("Name is required."))],
    )

    description = TextAreaField(_l("Description"))
