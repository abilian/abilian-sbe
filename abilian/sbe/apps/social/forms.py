# coding=utf-8
import imghdr
import PIL.Image

from wtforms.fields import StringField
from wtforms.validators import ValidationError
from wtforms_alchemy import model_form_factory

from wtforms import TextAreaField
from flask.ext.babel import gettext as _, lazy_gettext as _l

from abilian.web.forms import Form, widgets as abilian_widgets
from abilian.web.forms.fields import QuerySelect2Field
from abilian.web.forms.validators import required, optional
from abilian.web.forms.filters import strip

from abilian.sbe.apps.communities.models import Community

#from .widgets import UserPhotoInputWidget


ModelForm = model_form_factory(Form)


# FIXME
class UserProfileForm(ModelForm):

  #civilite = ContactEditForm.civilite
  #prenom = ContactEditForm.prenom
  #nom = ContactEditForm.nom
  #
  #titre = ContactEditForm.titre
  #
  #photo = FileField('Photo', widget=UserPhotoInputWidget(), validators=[optional()])
  #
  #telephone = ContactEditForm.telephone
  #adresse = ContactEditForm.adresse
  #code_postal = ContactEditForm.code_postal
  #ville = ContactEditForm.ville
  #pays = ContactEditForm.pays
  #fax = ContactEditForm.fax
  #mobile = ContactEditForm.mobile
  #url = ContactEditForm.url

  mail_2 = StringField('Mail 2', view_widget=abilian_widgets.EmailWidget(),
                     filters=(strip,), validators=[optional()])
  telephone_2 = StringField(u'T\xe9l\xe9phone 2', filters=(strip,),
                          validators=[optional()])
  fax_2 = StringField('Fax 2', filters=(strip,), validators=[optional()])
  mobile_2 = StringField('Mobile 2', filters=(strip,), validators=[optional()])
  url_2 = StringField('URL 2', filters=(strip,), validators=[optional()])
  mail_3 = StringField('Mail 3', filters=(strip,), validators=[optional()])
  telephone_3 = StringField(u'T\xe9l\xe9phone 3', filters=(strip,),
                          validators=[optional()])
  fax_3 = StringField('Fax 3', filters=(strip,), validators=[optional()])
  mobile_3 = StringField('Mobile 3', filters=(strip,), validators=[optional()])

  presentation = TextAreaField(u'Pr\xe9sentation', filters=(strip,),
                               validators=[optional()])
  cursus = TextAreaField('Cursus', filters=(strip,), validators=[optional()])
  expertise = TextAreaField('Expertise', filters=(strip,),
                            validators=[optional()])
  centres_interets = TextAreaField(u"Centres d'int\xe9r\xeats",
                                   filters=(strip,), validators=[optional()])

  def validate_photo(self, field):
    if not field.has_file():
      return

    data = field.data
    filename = data.filename
    valid = any(map(filename.lower().endswith, ('.png', '.jpg', '.jpeg')))

    if not valid:
      raise ValidationError(_(u'Only PNG or JPG image files are accepted'))

    img_type = imghdr.what('ignored', data.read())

    if not img_type in ('png', 'jpeg'):
      raise ValidationError(_(u'Only PNG or JPG image files are accepted'))

    data.stream.seek(0)
    try:
      # check this is actually an image file
      im = PIL.Image.open(data.stream)
      im.load()
    except:
      raise ValidationError(_(u'Could not decode image file'))

    data.stream.seek(0)

  _groups = [
   #  [u'Identité', [
   #    'civilite',
   #    'prenom',
   #    'nom',
   #    ]],
   #  [u'Photo', ['photo']],
   # [u'Partenaire', ['titre',]],
   #  [u'Coordonnées publiques', [
   #    'telephone',
   #    'adresse',
   #    'code_postal',
   #    'ville',
   #    'pays',
   #    'fax',
   #    'mobile',
   #    'url',
   #  ]],
    [u'Coordonnées privées', [
      'mail_2',
      'telephone_2',
      'fax_2',
      'mobile_2',
      'url_2',
      'mail_3',
      'telephone_3',
      'fax_3',
      'mobile_3',
    ]],
    [u'Informations complémentaires', [
      'presentation',
      'cursus',
      'expertise',
      'centres_interets',
    ]],
  ]


class UserProfileViewForm(UserProfileForm):

  communautes = QuerySelect2Field(
    u'Communautés d\'appartenance',
    get_label='name',
    view_widget=abilian_widgets.ListWidget(),
    query_factory=lambda: Community.query.all(),
    multiple=True,
    validators=[optional()])


class GroupForm(Form):

  name = StringField(_l("Name"),
                   filters=(strip,),
                   validators=[required(message=_l("Name is required."))])

  description = TextAreaField(_l("Description"))
