# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote

from flask import (
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
)
from flask_mail import Message
from PIL import Image
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from abilian.core.extensions import db, mail
from abilian.core.extensions.login import authenticated
from abilian.core.models import comment
from abilian.core.signals import activity
from abilian.core.sqlalchemy.session import session_of
from abilian.core.util import unwrap
from abilian.i18n import _, render_template_i18n
from abilian.sbe.apps.communities.common import object_viewers
from abilian.sbe.apps.communities.security import is_member
from abilian.sbe.apps.communities.views import default_view_kw
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.documents.repository import content_repository
from abilian.sbe.apps.documents.tasks import convert_document_content, preview_document
from abilian.services import audit_service
from abilian.services.audit.models import CREATION
from abilian.services.conversion import ConversionError, converter
from abilian.services.image import FIT, get_format, resize
from abilian.services.security import MANAGE, WRITE
from abilian.services.viewtracker import viewtracker
from abilian.web import csrf, url_for
from abilian.web.action import actions
from abilian.web.frontend import add_to_recent_items
from abilian.web.views import default_view

from .util import (
    breadcrumbs_for,
    check_manage_access,
    check_read_access,
    check_write_access,
    edit_object,
    get_document,
    get_folder,
    match,
)
from .views import community_blueprint

if TYPE_CHECKING:
    from collections.abc import Iterable

    from werkzeug.wrappers.response import Response

    from abilian.core.models.subjects import User
    from abilian.services.audit.models import AuditEntry

route = community_blueprint.route

MAX_PREVIEW_SIZE = 1000

__all__ = ()


def may_open(user: User, doc: Document) -> bool:
    """Whether `user` may open `doc`, as its page asks: a member of its community,
    who may read every folder it is in. Its comments ask the same."""
    return is_member(user, doc.community) and content_repository.has_access(user, doc)


comment.read_rule(Document, may_open)


def may_take_lock(user: User, doc: Document) -> bool:
    """Whether `user` may lock, or unlock, `doc`: anyone when it is free; when it
    is locked, whoever locked it, or one who manages it. No one else ends another's
    work, or takes it over."""
    lock = doc.lock
    return (
        lock is None
        or lock.is_owner(user)
        or content_repository.has_permission(user, MANAGE, doc)
    )


@default_view(community_blueprint, Document, id_attr="doc_id", kw_func=default_view_kw)
@route("/doc/<int:doc_id>")
@authenticated
def document_view(user: User, doc_id: int) -> str:
    doc = get_document(user, doc_id)
    check_read_access(user, doc)
    doc.ensure_antivirus_scheduled()
    db.session.commit()

    bc = breadcrumbs_for(doc)
    actions.context["object"] = doc

    if doc.content_type.startswith("image/"):
        add_to_recent_items(doc, "image")
    else:
        add_to_recent_items(doc, "document")

    viewtracker.record_hit(entity=doc, user=user)
    lock = doc.lock
    may_write = content_repository.has_permission(user, WRITE, doc)
    comments = current_app.extensions["comments"]
    doc_comments = comments.for_entity(doc)

    ctx = {
        "doc": doc,
        "breadcrumbs": bc,
        "lock": lock,
        "history": document_history(audit_service.entries_for(doc)),
        "has_preview": doc.has_preview(),
        "viewers": object_viewers(user, doc),
        "may_write": may_write,
        # A lock keeps the others from uploading a version (`document_upload`).
        "may_replace": may_write and (lock is None or lock.is_owner(user)),
        "may_unlock": may_write and may_take_lock(user, doc),
        "may_manage": content_repository.has_permission(user, MANAGE, doc),
        "doc_comments": doc_comments,
        "may_comment": comments.can_create(user, doc),
        # Their authors', and whoever may write them.
        "editable_comments": frozenset(
            c.id for c in doc_comments if comments.can_write(user, c)
        ),
        "deletable_comments": frozenset(
            c.id for c in doc_comments if comments.can_delete(user, c)
        ),
    }
    return render_template("documents/document.html", **ctx)


#: What a new version changes, and what editing a document's properties changes.
CONTENT_COLUMNS = frozenset({"_content_id", "content_digest"})
PROPERTY_COLUMNS = frozenset({"_title", "name", "description"})


@dataclass(frozen=True)
class Change:
    """A step in a document's history: who did what, and when.

    `kind` is "created", "new-version" or "edited".
    """

    kind: str
    user: User | None
    at: datetime


def document_history(entries: Iterable[AuditEntry]) -> tuple[Change, ...]:
    """The steps of a document's audit trail its readers care about, in its order.

    What they do not see changing (the conversion's results, the metadata) is left
    out.
    """
    kinds = ((entry, _change_kind(entry)) for entry in entries)
    # `happened_at` is set on insert by the column's default; the model types it
    # as nullable.
    return tuple(
        Change(kind, entry.user, entry.happened_at)
        for entry, kind in kinds
        if kind and entry.happened_at
    )


def _change_kind(entry: AuditEntry) -> str | None:
    if entry.type == CREATION:
        return "created"
    columns = entry.get_changes().columns.keys()
    if columns & CONTENT_COLUMNS:
        return "new-version"
    if columns & PROPERTY_COLUMNS:
        return "edited"
    return None


#
# Actions on documents
#
@route("/doc/<int:doc_id>/", methods=["POST"])
@route("/doc/<int:doc_id>/<int:folder_id>/", methods=["POST"])
@csrf.protect
# TODO: URL doesn't seem right
@authenticated
def document_edit(user: User, doc_id, folder_id=None):
    doc = get_document(user, doc_id)
    if folder_id:
        folder = get_folder(user, folder_id)
    else:
        folder = None
    check_write_access(user, doc)

    changed = edit_object(doc)

    if changed:
        db.session.commit()
        flash(_("Document properties successfully edited."), "success")
    else:
        flash(_("You didn't change any property."), "success")

    if folder:
        return redirect(url_for(folder))
    return redirect(url_for(doc))


@route("/doc/<int:doc_id>/viewers", methods=["GET"])
@authenticated
def document_viewers(user: User, doc_id):
    doc = get_document(user, doc_id)
    check_read_access(user, doc)
    ctx = {
        "doc": doc,
        "breadcrumbs": breadcrumbs_for(doc),
        "viewers": object_viewers(user, doc),
    }
    return render_template("documents/document_viewers.html", **ctx)


@route("/doc/<int:doc_id>/delete", methods=["POST"])
@csrf.protect
@authenticated
def document_delete(user: User, doc_id: int) -> Response:
    doc = get_document(user, doc_id)
    check_write_access(user, doc)

    parent_folder = doc.parent
    content_repository.delete_object(doc)
    db.session.commit()

    flash(_("File successfully deleted."), "success")
    return redirect(url_for(parent_folder))


@route("/doc/<int:doc_id>/upload", methods=["POST"])
@csrf.protect
@authenticated
def document_upload(user: User, doc_id):
    doc = get_document(user, doc_id)
    check_write_access(user, doc)
    # Whoever locked it is working on it: a version from someone else would be lost.
    if doc.lock and not doc.lock.is_owner(user):
        raise Forbidden

    fd = request.files["file"]
    doc.set_content(fd.read(), fd.content_type)
    del doc.lock

    self = unwrap(current_app)
    activity.send(self, actor=user, verb="update", object=doc)
    db.session.commit()
    flash(_("New version successfully uploaded"), "success")
    return redirect(url_for(doc))


@route("/doc/<int:doc_id>/download")
@authenticated
def document_download(user: User, doc_id: int, attach: bool = False) -> Response:
    """Download the file content."""
    doc = get_document(user, doc_id)

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
        response.headers["content-disposition"] = (
            f'attachment;filename="{quoted_filename}"'
        )

    return response


@route("/doc/<int:doc_id>/checkin_checkout", methods=["POST"])
@authenticated
def checkin_checkout(user: User, doc_id):
    doc = get_document(user, doc_id)
    check_write_access(user, doc)
    if not may_take_lock(user, doc):
        raise Forbidden
    action = request.form.get("action")

    if action not in ("checkout", "lock", "unlock"):
        msg = f"Unknown action: {action!r}"
        raise BadRequest(msg)

    session = session_of(doc)

    if action in ("lock", "checkout"):
        doc.lock = user
        d = doc.updated_at
        # prevent change of last modification date
        doc.updated_at = datetime.utcnow()
        session.flush()
        doc.updated_at = d
        session.commit()

        match action:
            case "lock":
                return redirect(url_for(doc))
            case "checkout":
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
    return None


def preview_missing_image():
    response = redirect(
        url_for("abilian_sbe_static", filename="images/preview_missing.png")
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


@route("/doc/<int:doc_id>/preview_image")
@authenticated
def document_preview_image(user: User, doc_id: int) -> Response:
    """Returns a preview (image) for the file given by its id."""

    doc = get_document(user, doc_id)

    if not doc.antivirus_ok:
        return preview_missing_image()

    # `Blob.value` is None when the row survives but its file does not -- a
    # database restored without its file store, a pruned repository. Every
    # branch below needs the content, so this is the one place to say so;
    # without it the image branch reached resize(None, ...) and 500ed.
    if not doc.content:
        return preview_missing_image()

    size = int(request.args.get("size", 0))

    # Just in case
    size = min(size, MAX_PREVIEW_SIZE)

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
        # Not the default: resizing keeps a PNG a PNG.
        if image:
            content_type = Image.MIME[get_format(image)]
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
@authenticated
def refresh_preview(user: User, doc_id):
    """Force to compute a new preview."""
    doc = get_document(user, doc_id)
    if not doc:
        raise NotFound

    ct = doc.find_content_type(doc.content_type)
    if ct != doc.content_type:
        doc.content_type = ct
        db.session.commit()

    check_manage_access(user, doc)
    # Taken first: the tasks close the request's session, detaching the document.
    url = url_for(doc)
    # convert_document_content.apply([doc_id])
    with contextlib.suppress(ConversionError, OSError):
        convert_document_content(doc_id)
    # preview_document.apply([doc_id])
    with contextlib.suppress(ConversionError, OSError):
        preview_document(doc_id)
    return redirect(url)


@route("/doc/<int:doc_id>/send", methods=["POST"])
@csrf.protect
@authenticated
def document_send(user: User, doc_id: int) -> Response:
    doc = get_document(user, doc_id)

    recipient = request.form.get("recipient")
    user_msg = request.form.get("message")

    site_name = f"[{current_app.config['SITE_NAME']}] "
    sender_name = user.name
    subject = site_name + _("{sender} sent you a file").format(sender=sender_name)
    msg = Message(subject)
    msg.sender = user.email
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
@authenticated
def document_preview(user: User, doc_id):
    doc = get_document(user, doc_id)
    if not doc.antivirus_ok:
        return "Waiting for antivirus to finish"

    if doc.content_type == "application/pdf":
        return redirect(
            url_for(".document_view_pdf", community_id=g.community.slug, doc_id=doc.id)
        )

    return redirect(
        url_for(".document_download", community_id=g.community.slug, doc_id=doc.id)
    )


@route("/doc/<int:doc_id>/view_pdf")
@authenticated
def document_view_pdf(user: User, doc_id):
    doc = get_document(user, doc_id)
    if not doc.antivirus_ok:
        return "Waiting for antivirus to finish"

    return render_template(
        "documents/view_pdf.html",
        doc=doc,
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
#     doc = get_document(user, file_id)
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
