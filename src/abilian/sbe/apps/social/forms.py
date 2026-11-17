# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from wtforms import StringField, TextAreaField
from wtforms_alchemy import model_form_factory

from abilian.i18n import _l
from abilian.web.forms import Form
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import required

ModelForm: type[Form] = model_form_factory(Form)


class UserProfileForm(ModelForm):
    pass


class GroupForm(Form):
    name = StringField(
        _l("Name"),
        filters=(strip,),
        validators=[required(message=_l("Name is required."))],
    )

    description = TextAreaField(_l("Description"))
