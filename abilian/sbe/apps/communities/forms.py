import imghdr
from string import strip
import PIL

from flask import request
from flask.ext.babel import lazy_gettext as _l, gettext as _
from wtforms.fields import BooleanField, TextField, TextAreaField
from wtforms.validators import ValidationError, required

from abilian.web.forms import Form
from abilian.web.forms.fields import Select2Field, FileField
from abilian.web.forms.widgets import TextArea, ImageInput, BooleanWidget
from abilian.web.forms.validators import length

from .models import Community


class CommunityForm(Form):
  name = TextField(label=_l(u"Name"), validators=[required()])
  description = TextAreaField(
      label=_l(u"Description"),
      validators=[required(), length(max=500)],
      widget=TextArea(resizeable="vertical"),)

  image = FileField(label=_l('Image'), widget=ImageInput(width=65, height=65),
                    allow_delete=False)

  type = Select2Field(label=_(u"Type"), validators=[required()],
                      filters=(strip,),
                      choices=[(_l(u'informative'), 'informative'),
                               (_l(u'participative'), 'participative')])

  has_documents = BooleanField(label=_l(u"Has documents"),
                               widget=BooleanWidget(on_off_mode=True))
  has_wiki = BooleanField(label=_l(u"Has a wiki"),
                          widget=BooleanWidget(on_off_mode=True))
  has_forum = BooleanField(label=_l(u"Has a forum"),
                           widget=BooleanWidget(on_off_mode=True))

  def validate_name(self, field):
    name = field.data = field.data.strip()

    if name and field.object_data:
      # form is bound to an existing object, name is not empty
      if name != field.object_data:
        # name changed: check for duplicates
        if len(list(Community.query.filter(Community.name==name).values('id'))) > 0:
          raise ValidationError(_(u"A community with this name already exists"))

  def validate_description(self, field):
    field.data = field.data.strip()

  # FIXME: code duplicated from the user edit form (UserProfileForm).
  # Needs to be refactored.
  def validate_image(self, field):
    data = request.files.get('image')
    if not data:
      return

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
    field.data = data
