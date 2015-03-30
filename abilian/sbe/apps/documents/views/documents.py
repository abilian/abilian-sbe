# coding=utf-8
"""
"""
from __future__ import absolute_import

from urllib import quote

from flask import (redirect, request, make_response, flash, g,
                   current_app, render_template, abort)
from flask.ext.mail import Message
from flask.ext.babel import gettext as _

from abilian.i18n import render_template_i18n
from abilian.core.extensions import db, mail
from abilian.core.signals import activity
from abilian.services import audit_service
from abilian.services.image import resize
from abilian.services.conversion import converter
from abilian.web.action import actions
from abilian.web.frontend import add_to_recent_items
from abilian.web.views import default_view
from abilian.web import csrf, url_for

from abilian.sbe.apps.communities.views import default_view_kw

from ..tasks import preview_document, convert_document_content
from ..repository import repository
from ..models import Document

from .util import get_document, check_read_access, breadcrumbs_for, \
  check_write_access, edit_object, match, check_manage_access
from .views import documents


route = documents.route

MAX_PREVIEW_SIZE = 1000


@default_view(documents, Document, id_attr='doc_id', kw_func=default_view_kw)
@route("/doc/<int:doc_id>")
def document_view(doc_id):
  doc = get_document(doc_id)
  check_read_access(doc)
  doc.ensure_antivirus_scheduled()
  db.session.commit()

  bc = breadcrumbs_for(doc)
  actions.context['object'] = doc

  if doc.content_type.startswith("image/"):
    add_to_recent_items(doc, "image")
  else:
    add_to_recent_items(doc, "document")

  has_preview = doc.has_preview()
  audit_entries = audit_service.entries_for(doc)

  ctx = dict(doc=doc, audit_entries=audit_entries, breadcrumbs=bc,
             folder=doc.parent,
             has_preview=has_preview,
             csrf_token=csrf.field())
  return render_template("documents/document.html", **ctx)


#
# Actions on documents
#
@route("/doc/<int:doc_id>", methods=['POST'])
@csrf.protect
def document_edit(doc_id):
  doc = get_document(doc_id)
  check_write_access(doc)

  changed = edit_object(doc)

  if changed:
    db.session.commit()
    flash(_(u"Document properties successfully edited."), "success")
  else:
    flash(_(u"You didn't change any property."), "success")

  return redirect(url_for(doc))


@route("/doc/<int:doc_id>/delete", methods=['POST'])
@csrf.protect
def document_delete(doc_id):
  doc = get_document(doc_id)
  check_write_access(doc)

  parent_folder = doc.parent
  repository.delete_object(doc)
  db.session.commit()

  flash(_(u"File successfully deleted."), "success")
  return redirect(url_for(parent_folder))


@route("/doc/<int:doc_id>/upload", methods=['POST'])
@csrf.protect
def document_upload(doc_id):
  doc = get_document(doc_id)
  check_write_access(doc)

  fd = request.files['file']
  doc.set_content(fd.read(), fd.content_type)

  self = current_app._get_current_object()
  activity.send(self, actor=g.user, verb="update", object=doc)

  db.session.commit()

  flash(_(u"New version successfully uploaded"), "success")
  return redirect(url_for(doc))


@route("/doc/<int:doc_id>/download")
def document_download(doc_id):
  """Download the file content."""

  doc = get_document(doc_id)

  response = make_response(doc.content)
  response.headers['content-length'] = doc.content_length
  response.headers['content-type'] = doc.content_type

  attach = request.args.get('attach')
  if attach or \
    not match(doc.content_type, ("text/plain", "application/pdf", "image/*")):
    # Note: we omit text/html for security reasons.
    quoted_filename = quote(doc.title.encode('utf8'))
    response.headers[
      'content-disposition'] = 'attachment;filename="%s"' % quoted_filename

  return response


def preview_missing_image():
  response = redirect(
    url_for('static', filename='images/preview_missing.png'))
  response.headers['Cache-Control'] = 'no-cache'
  return response


@route("/doc/<int:doc_id>/preview")
def document_preview(doc_id):
  """Returns a preview (image) for the file given by its id."""

  doc = get_document(doc_id)

  if not doc.antivirus_ok:
    return preview_missing_image()

  size = int(request.args.get("size", 0))

  # Just in case
  if size > MAX_PREVIEW_SIZE:
    size = MAX_PREVIEW_SIZE

  # compute image if size != standard document size
  get_image = (converter.get_image
               if size == doc.preview_size
               else converter.to_image)

  content_type = "image/jpeg"

  if doc.content_type.startswith('image/svg'):
    image = doc.content
    content_type = doc.content_type
  elif doc.content_type.startswith("image/"):
    image = doc.content
    if size:
      image = resize(image, size)
  else:
    page = int(request.args.get("page", 0))
    try:
      image = get_image(doc.digest, doc.content, doc.content_type, page, size)
    except:
      # TODO: use generic "conversion failed" image
      image = ""

  if not image:
    return preview_missing_image()

  response = make_response(image)
  response.headers['content-type'] = content_type
  return response


@route("/doc/<int:doc_id>/refresh_preview")
def refresh_preview(doc_id):
  """ Force to compute a new preview
  """
  doc = get_document(doc_id)
  if not doc:
    abort(404)

  ct = doc.find_content_type(doc.content_type)
  if ct != doc.content_type:
    doc.content_type = ct
    db.session.commit()

  check_manage_access(doc)
  convert_document_content(doc_id)
  preview_document(doc_id)
  return redirect(url_for(doc))


@route("/doc/<int:doc_id>/send", methods=['POST'])
@csrf.protect
def document_send(doc_id):
  doc = get_document(doc_id)

  recipient = request.form.get("recipient")
  user_msg = request.form.get('message')

  site_name = u'[{}] '.format(current_app.config['SITE_NAME'])
  sender_name = g.user.name
  subject = site_name + _(u'{sender} sent you a file').format(sender=sender_name)
  msg = Message(subject)
  msg.sender = g.user.email
  msg.recipients = [recipient]
  msg.body = render_template_i18n('documents/mail_file_sent.txt',
                                  sender_name=sender_name,
                                  message=user_msg,
                                  document_url=url_for(doc),
                                  filename=doc.title)

  filename = doc.title
  msg.attach(filename, doc.content_type, doc.content)

  mail.send(msg)
  flash(_(u"Email successfully sent"), "success")

  return redirect(url_for(doc))


#
# Tagging (currently not used!)
#
#@route("/tag")
#def tag():
#  tag = request.args.get("tag")
#  if not tag:
#    return redirect("/dm/")
#
#  bc = [dict(path="/", label="Home"), dict(path="/dm/", label="DM")]
#  bc += [dict(path=request.path, label="Filter by tag")]
#  # TODO ...
#  docs = Document.query.filter(Document.tags.like("%" + tag + "%"))
#  docs = list(docs.all())
#  docs = [f for f in docs if tag in f.tags.split(",")]
#  title = "Files filtered by tag: %s" % tag
#  return render_template("dm/home.html", title=title, breadcrumbs=bc,
# files=docs)
#
#
#@route("/<int:file_id>/tag", methods=['POST'])
#def tag_post(file_id):
#  doc = get_document(file_id)
#  tags = request.form.get("tags")
#
#  doc.tags = tags
#  self = current_app._get_current_object()
#  activity.send(self, actor=g.user, verb="tag", object=doc)
#
#  db.session.commit()
#
#  flash("Tags successfully successfully updated", "success")
#  return redirect(url_for(".document_view", doc_id=doc.id))
