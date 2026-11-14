# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import sqlalchemy as sa
from flask import request
from wtforms import BooleanField, StringField, TextAreaField
from wtforms.validators import ValidationError, data_required, optional

from abilian.core.models.subjects import Group
from abilian.i18n import _, _l
from abilian.web.forms import Form
from abilian.web.forms.fields import ChoiceField, FileField
from abilian.web.forms.validators import length, open_png_or_jpeg
from abilian.web.forms.widgets import BooleanWidget, ImageInput, TextArea

from .models import Community


def strip(s: str) -> str:
    if s is None:
        # FIXME: this should not happen, but currently it does
        return ""
    return s.strip()


def _group_choices() -> list[tuple[str, str]]:
    m_prop = Group.members.property
    membership = m_prop.secondary
    query = Group.query.session.query(
        Group.id,
        Group.name,
        Community.name.label("community"),
        sa.sql.func.count(membership.c.user_id).label("members_count"),
    )
    query = (
        query.outerjoin(m_prop.secondary, m_prop.primaryjoin)
        .outerjoin(Community, Community.group.property.primaryjoin)
        .group_by(Group.id, Group.name, Community.name)
        .order_by(sa.sql.func.lower(Group.name))
        .autoflush(False)
    )
    choices = [("", "")]

    for g in query:
        label = f"{g.name} ({g.members_count:d} membres)"
        if g.community:
            label += f" — Communauté: {g.community}"
        choices.append((str(g.id), label))

    return choices


class CommunityForm(Form):
    name = StringField(label=_l("Name"), validators=[data_required()])
    description = TextAreaField(
        label=_l("Description"),
        validators=[data_required(), length(max=500)],
        widget=TextArea(resizeable="vertical"),
    )

    linked_group = ChoiceField(
        label=_l("Linked to group"),
        description=_l("Manages a group of users through this community members."),
        choices=_group_choices,
    )

    image = FileField(
        label=_l("Image"),
        widget=ImageInput(width=65, height=65),
        validators=[optional()],
    )

    type = ChoiceField(
        label=_("Type"),
        validators=[data_required()],
        filters=(strip,),
        choices=[
            (_l("informative"), "informative"),
            (_l("participative"), "participative"),
        ],
    )

    has_documents = BooleanField(label=_l("Has documents"), widget=BooleanWidget())
    has_wiki = BooleanField(label=_l("Has a wiki"), widget=BooleanWidget())
    has_forum = BooleanField(label=_l("Has a forum"), widget=BooleanWidget())

    def validate_name(self, field: StringField) -> None:
        name = field.data = field.data.strip()

        if not name:
            return

        if not field.object_data:
            return

        # form is bound to an existing object, name is not empty
        if name == field.object_data:
            return

        # name changed: check for duplicates
        if Community.query.filter(Community.name == name).count() > 0:
            raise ValidationError(_("A community with this name already exists"))

    def validate_description(self, field: TextAreaField) -> None:
        field.data = field.data.strip()

    def validate_image(self, field) -> None:
        if not request.form.get("image"):
            return
        open_png_or_jpeg(field.data)
