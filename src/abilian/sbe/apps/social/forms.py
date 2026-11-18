# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from wtforms_alchemy import model_form_factory

from abilian.web.forms import Form

ModelForm: type[Form] = model_form_factory(Form)


class UserProfileForm(ModelForm):
    pass
