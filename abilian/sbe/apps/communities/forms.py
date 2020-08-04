import imghdr
from typing import List, Tuple

import sqlalchemy as sa
from flask import request
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from PIL import Image
from wtforms.fields import BooleanField
from wtforms.fields.core import StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import ValidationError, data_required, optional

from abilian.core.models.subjects import Group
from abilian.web.forms import Form
from abilian.web.forms.fields import FileField, Select2Field
from abilian.web.forms.validators import length
from abilian.web.forms.widgets import BooleanWidget, ImageInput, TextArea

from .models import Community


def strip(s: str) -> str:
    return s.strip()


def _group_choices() -> List[Tuple[str, str]]:
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

    linked_group = Select2Field(
        label=_l("Linked to group"),
        description=_l("Manages a group of users through this community members."),
        choices=_group_choices,
    )

    image = FileField(
        label=_l("Image"),
        widget=ImageInput(width=65, height=65),
        validators=[optional()],
    )

    type = Select2Field(
        label=_("Type"),
        validators=[data_required()],
        filters=(strip,),
        choices=[
            (_l("informative"), "informative"),
            (_l("participative"), "participative"),
        ],
    )

    has_documents = BooleanField(
        label=_l("Has documents"), widget=BooleanWidget(on_off_mode=True)
    )
    has_wiki = BooleanField(
        label=_l("Has a wiki"), widget=BooleanWidget(on_off_mode=True)
    )
    has_forum = BooleanField(
        label=_l("Has a forum"), widget=BooleanWidget(on_off_mode=True)
    )

    def validate_name(self, field: StringField) -> None:
        name = field.data = field.data.strip()

        if name and field.object_data:
            # form is bound to an existing object, name is not empty
            if name != field.object_data:
                # name changed: check for duplicates
                if Community.query.filter(Community.name == name).count() > 0:
                    raise ValidationError(
                        _("A community with this name already exists")
                    )

    def validate_description(self, field: TextAreaField) -> None:
        field.data = field.data.strip()

    # FIXME: code duplicated from the user edit form (UserProfileForm).
    # Needs to be refactored.
    def validate_image(self, field):
        data = request.form.get("image")
        if not data:
            return

        data = field.data
        filename = data.filename
        valid = any(map(filename.lower().endswith, (".png", ".jpg", ".jpeg")))

        if not valid:
            raise ValidationError(_("Only PNG or JPG image files are accepted"))

        img_type = imghdr.what("ignored", data.read())

        if img_type not in ("png", "jpeg"):
            raise ValidationError(_("Only PNG or JPG image files are accepted"))

        data.seek(0)
        try:
            # check this is actually an image file
            im = Image.open(data)
            im.load()
        except BaseException:
            raise ValidationError(_("Could not decode image file"))

        data.seek(0)
        field.data = data
