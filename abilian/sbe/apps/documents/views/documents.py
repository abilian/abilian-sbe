from datetime import datetime
from urllib.parse import quote

import sqlalchemy as sa
import sqlalchemy.orm
from flask import current_app, flash, g, make_response, redirect, \
    render_template, request
from flask_login import current_user
from flask_mail import Message
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.wrappers.response import Response

from abilian.core.extensions import db, mail
from abilian.core.signals import activity
from abilian.core.util import unwrap
from abilian.i18n import _, render_template_i18n
from abilian.sbe.apps.communities.common import object_viewers
from abilian.sbe.apps.communities.views import default_view_kw
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.documents.repository import repository
from abilian.sbe.apps.documents.tasks import convert_document_content, \
    preview_document
from abilian.services import audit_service
from abilian.services.conversion import converter
from abilian.services.image import FIT, resize
from abilian.services.viewtracker import viewtracker
from abilian.web import csrf, url_for
from abilian.web.action import actions
from abilian.web.frontend import add_to_recent_items
from abilian.web.views import default_view

from .util import breadcrumbs_for, check_manage_access, check_read_access, \
    check_write_access, edit_object, get_document, get_folder, match
from .views import blueprint

route = blueprint.route

MAX_PREVIEW_SIZE = 1000

__all__ = ()


@default_view(blueprint, Document, id_attr="doc_id", kw_func=default_view_kw)
@route("/doc/<int:doc_id>")
def document_view(doc_id: int) -> str:
    doc = get_document(doc_id)
    check_read_access(doc)
    doc.ensure_antivirus_scheduled()
    db.session.commit()

    bc = breadcrumbs_for(doc)
    actions.context["object"] = doc

    if doc.content_type.startswith("image/"):
        add_to_recent_items(doc, "image")
    else:
        add_to_recent_items(doc, "document")

    has_preview = doc.has_preview()
    audit_entries = audit_service.entries_for(doc)
    viewtracker.record_hit(entity=doc, user=current_user)

    ctx = {
        "doc": doc,
        "audit_entries": audit_entries,
        "breadcrumbs": bc,
        "folder": doc.parent,
        "has_preview": has_preview,
        "viewers": object_viewers(doc),
    }
    return render_template("documents/document.html", **ctx)


#
# Actions on documents
#
@route("/doc/<int:doc_id>/", methods=["POST"])
@route("/doc/<int:doc_id>/<int:folder_id>/", methods=["POST"])
@csrf.protect
# TODO: URL doesn't seem right
def document_edit(doc_id, folder_id=None):
    doc = get_document(doc_id)
    if folder_id:
        folder = get_folder(folder_id)
    else:
        folder = None
    check_write_access(doc)

    changed = edit_object(doc)

    if changed:
        db.session.commit()
        flash(_("Document properties successfully edited."), "success")
    else:
        flash(_("You didn't change any property."), "success")

    if folder:
        return redirect(url_for(folder))
    else:
        return redirect(url_for(doc))


@route("/doc/<int:doc_id>/viewers", methods=["GET"])
def document_viewers(doc_id):
    doc = get_document(doc_id)
    check_read_access(doc)
    doc.ensure_antivirus_scheduled()
    # db.session.commit()

    bc = breadcrumbs_for(doc)
    actions.context["object"] = doc
    """if doc.content_type.startswith("image/"):
        add_to_recent_items(doc, "image")
    else:
        add_to_recent_items(doc, "document")"""

    has_preview = doc.has_preview()
    audit_entries = audit_service.entries_for(doc)

    ctx = {
        "doc": doc,
        "audit_entries": audit_entries,
        "breadcrumbs": bc,
        "folder": doc.parent,
        "has_preview": has_preview,
        "viewers": object_viewers(doc),
    }
    return render_template("documents/document_viewers.html", **ctx)


@route("/doc/<int:doc_id>/delete", methods=["POST"])
@csrf.protect
def document_delete(doc_id: int) -> Response:
    doc = get_document(doc_id)
    check_write_access(doc)

    parent_folder = doc.parent
    repository.delete_object(doc)
    db.session.commit()

    flash(_("File successfully deleted."), "success")
    return redirect(url_for(parent_folder))


@route("/doc/<int:doc_id>/upload", methods=["POST"])
@csrf.protect
def document_upload(doc_id):
    doc = get_document(doc_id)
    check_write_access(doc)

    fd = request.files["file"]
    doc.set_content(fd.read(), fd.content_type)
    del doc.lock

    self = unwrap(current_app)
    activity.send(self, actor=current_user, verb="update", object=doc)
    db.session.commit()
    flash(_("New version successfully uploaded"), "success")
    return redirect(url_for(doc))


@route("/doc/<int:doc_id>/download")
def document_download(doc_id: int, attach: bool = False) -> Response:
    """Download the file content."""
    doc = get_document(doc_id)

    response = make_response(doc.content)
    response.headers["content-length"] = doc.content_length
    response.headers["content-type"] = doc.content_type

    if not attach:
        attach = request.args.get("attach", False)

    if attach or not match(
        doc.content_type, ("text/plain", "application/pdf", "image/*")
    ):
        # Note: we omit text/html for security reasons.
        quoted_filename = quote(doc.title.encode("utf8"))
        response.headers["content-disposition"] = 'attachment;filename="{}"'.format(
            quoted_filename
        )

    return response


@route("/doc/<int:doc_id>/checkin_checkout", methods=["POST"])
def checkin_checkout(doc_id):
    doc = get_document(doc_id)
    action = request.form.get("action")

    if action not in ("checkout", "lock", "unlock"):
        raise BadRequest(f"Unknown action: {action!r}")

    session = sa.orm.object_session(doc)

    if action in ("lock", "checkout"):
        doc.lock = current_user
        d = doc.updated_at
        # prevent change of last modification date
        doc.updated_at = datetime.utcnow()
        session.flush()
        doc.updated_at = d
        session.commit()

        if action == "lock":
            return redirect(url_for(doc))
        elif action == "checkout":
            return document_download(doc_id, attach=True)

    if action == "unlock":
        del doc.lock
        d = doc.updated_at
        # prevent change of last modification date
        doc.updated_at = datetime.utcnow()
        session.flush()
        doc.updated_at = d
        session.commit()
        return redirect(url_for(doc))


def preview_missing_image():
    response = redirect(
        url_for("abilian_sbe_static", filename="images/preview_missing.png")
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


@route("/doc/<int:doc_id>/preview_image")
def document_preview_image(doc_id: int) -> Response:
    """Returns a preview (image) for the file given by its id."""

    doc = get_document(doc_id)

    if not doc.antivirus_ok:
        return preview_missing_image()

    size = int(request.args.get("size", 0))

    # Just in case
    if size > MAX_PREVIEW_SIZE:
        size = MAX_PREVIEW_SIZE

    # compute image if size != standard document size
    get_image = converter.get_image if size == doc.preview_size else converter.to_image

    content_type = "image/jpeg"

    if doc.content_type.startswith("image/svg"):
        image = doc.content
        content_type = doc.content_type
    elif doc.content_type.startswith("image/"):
        image = doc.content
        if size:
            image = resize(image, size, size, mode=FIT)
    else:
        page = int(request.args.get("page", 0))
        try:
            image = get_image(doc.digest, doc.content, doc.content_type, page, size)
        except BaseException:
            # TODO: use generic "conversion failed" image
            image = ""

    if not image:
        return preview_missing_image()

    response = make_response(image)
    response.headers["content-type"] = content_type
    return response


@route("/doc/<int:doc_id>/refresh_preview")
def refresh_preview(doc_id):
    """Force to compute a new preview."""
    doc = get_document(doc_id)
    if not doc:
        raise NotFound()

    ct = doc.find_content_type(doc.content_type)
    if ct != doc.content_type:
        doc.content_type = ct
        db.session.commit()

    check_manage_access(doc)
    convert_document_content.apply([doc_id])
    preview_document.apply([doc_id])
    return redirect(url_for(doc))


@route("/doc/<int:doc_id>/send", methods=["POST"])
@csrf.protect
def document_send(doc_id: int) -> Response:
    doc = get_document(doc_id)

    recipient = request.form.get("recipient")
    user_msg = request.form.get("message")

    site_name = f"[{current_app.config['SITE_NAME']}] "
    sender_name = current_user.name
    subject = site_name + _("{sender} sent you a file").format(sender=sender_name)
    msg = Message(subject)
    msg.sender = current_user.email
    msg.recipients = [recipient]
    msg.body = render_template_i18n(
        "documents/mail_file_sent.txt",
        sender_name=sender_name,
        message=user_msg,
        document_url=url_for(doc),
        filename=doc.title,
    )

    filename = doc.title
    msg.attach(filename, doc.content_type, doc.content)

    mail.send(msg)
    flash(_("Email successfully sent"), "success")

    return redirect(url_for(doc))


@route("/doc/<int:doc_id>/preview")
def document_preview(doc_id):
    doc = get_document(doc_id)
    if not doc.antivirus_ok:
        return "Waiting for antivirus to finish"

    if doc.content_type == "application/pdf":
        return redirect(
            url_for(".document_view_pdf", community_id=g.community.slug, doc_id=doc.id)
        )

    else:
        return redirect(
            url_for(".document_download", community_id=g.community.slug, doc_id=doc.id)
        )


@route("/doc/<int:doc_id>/view_pdf")
def document_view_pdf(doc_id):
    doc = get_document(doc_id)
    if not doc.antivirus_ok:
        return "Waiting for antivirus to finish"

    return render_template(
        "documents/view_pdf.html",
        pdf_url=url_for(
            ".document_download", community_id=g.community.slug, doc_id=doc.id
        ),
    )


#
# Tagging (currently not used!)
#
# @route("/tag")
# def tag():
#     tag = request.args.get("tag")
#     if not tag:
#         return redirect("/dm/")
#
#     bc = [dict(path="/", label="Home"), dict(path="/dm/", label="DM")]
#     bc += [dict(path=request.path, label="Filter by tag")]
#     # TODO ...
#     docs = Document.query.filter(Document.tags.like("%" + tag + "%"))
#     docs = list(docs.all())
#     docs = [f for f in docs if tag in f.tags.split(",")]
#     title = "Files filtered by tag: %s" % tag
#     return render_template("dm/home.html", title=title, breadcrumbs=bc,
#                            files=docs)
#
#
# @route("/<int:file_id>/tag", methods=['POST'])
# def tag_post(file_id):
#     doc = get_document(file_id)
#     tags = request.form.get("tags")
#
#     doc.tags = tags
#     self = unwrap(current_app)
#     activity.send(self, actor=g.user, verb="tag", object=doc)
#
#     db.session.commit()
#
#     flash("Tags successfully successfully updated", "success")
#     return redirect(url_for(".document_view", doc_id=doc.id))
