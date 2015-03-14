# coding=utf-8

from wtforms.fields import StringField
from wtforms_alchemy import model_form_factory

from wtforms import TextAreaField
from flask.ext.babel import lazy_gettext as _l

from abilian.web.forms import Form, widgets as abilian_widgets
from abilian.web.forms.fields import QuerySelect2Field
from abilian.web.forms.validators import required, optional
from abilian.web.forms.filters import strip

from abilian.sbe.apps.communities.models import Community

#from .widgets import UserPhotoInputWidget


ModelForm = model_form_factory(Form)


# FIXME
class UserProfileForm(ModelForm):
  pass


class UserProfileViewForm(UserProfileForm):
  communautes = QuerySelect2Field(
    u'Communautés d\'appartenance',
    get_label='name',
    view_widget=abilian_widgets.ListWidget(),
    query_factory=lambda: Community.query.all(),
    multiple=True,
    validators=[optional()])


class GroupForm(Form):
  name = StringField(
    _l("Name"),
    filters=(strip,),
    validators=[required(message=_l("Name is required."))])

  description = TextAreaField(_l("Description"))
