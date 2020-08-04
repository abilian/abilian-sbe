from flask_babel import lazy_gettext as _l
from wtforms import StringField, TextAreaField
from wtforms_alchemy import model_form_factory

from abilian.sbe.apps.communities.models import Community
from abilian.web.forms import Form
from abilian.web.forms import widgets as abilian_widgets
from abilian.web.forms.fields import QuerySelect2Field
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import optional, required

ModelForm = model_form_factory(Form)  # type: Form


class UserProfileForm(ModelForm):
    pass


class UserProfileViewForm(UserProfileForm):
    communautes = QuerySelect2Field(
        "Communautés d'appartenance",
        get_label="name",
        view_widget=abilian_widgets.ListWidget(),
        query_factory=lambda: Community.query.all(),
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
