# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm
from flask import current_app, send_file
from werkzeug.exceptions import BadRequest, Forbidden
from werkzeug.utils import redirect

from abilian.core.application import as_application
from abilian.core.entities import Entity
from abilian.core.models.attachment import Attachment, supports_attachments
from abilian.i18n import _, _l
from abilian.web import nav, url_for
from abilian.web.access_blueprint import AccessControlBlueprint
from abilian.web.action import ButtonAction, actions
from abilian.web.views import BaseObjectView, ObjectCreate, ObjectDelete, ObjectEdit

from .forms import AttachmentForm

if TYPE_CHECKING:
    from flask.blueprints import BlueprintSetupState

bp = AccessControlBlueprint("attachments", __name__, url_prefix="/attachments")


def _default_attachment_view(obj, obj_type, obj_id, **kwargs):
    if not hasattr(obj, "entity"):
        return url_for("attachments.entity", object_id=obj_id)
    entity = obj.entity
    return url_for(entity, _anchor=f"attachment-{obj.id}")


@bp.record_once
def register_default_view(state: BlueprintSetupState) -> None:
    as_application(state.app).default_view.register(
        Attachment, _default_attachment_view
    )


UPLOAD_BUTTON = ButtonAction("form", "edit", btn_class="primary", title=_l("Send"))


class BaseAttachmentView:
    """Mixin for attachment views."""

    Model = Attachment
    Form = AttachmentForm

    #: The capability on the *owning entity* that this view needs. An
    #: attachment's permissions are its owner's: you may do X to an attachment
    #: if and only if you may do X to what it hangs off.
    capability = "can_read"

    #: owning entity
    entity: Entity | None = None

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        entity_id = kwargs.pop("entity_id", None)

        if entity_id is not None:
            self.entity = Entity.query.get(entity_id)

        if self.entity is None:
            msg = "No entity provided"
            raise BadRequest(msg)

        if not supports_attachments(self.entity):
            msg = "This entity is doesn't support attachments"
            raise BadRequest(msg)

        extension = current_app.extensions["attachments"]
        manager = extension.manager(self.entity)

        # Nothing used to check anything here. The capabilities existed on the
        # manager and were consulted only by a template the app never renders,
        # so every route was open to any authenticated user -- unreachable
        # only because no model is registered attachable. See
        # notes/plan-attachments.md.
        if not getattr(manager, self.capability)(self.entity):
            raise Forbidden

        self.Form = manager.Form
        actions.context["object"] = self.entity
        return args, kwargs

    def view_url(self):
        kw = {}
        if self.obj and self.obj.id:
            kw["_anchor"] = f"attachment-{self.obj.id}"
        return url_for(self.entity, **kw)

    def index_url(self):
        return self.view_url()

    @property
    def activity_target(self):
        return self.entity


class AttachmentDownload(BaseAttachmentView, BaseObjectView):
    def get(self):
        blob = self.obj.blob
        metadata = blob.meta
        filename = metadata.get("filename", self.obj.name)
        content_type = metadata.get("mimetype")
        stream = blob.file.open("rb")

        # `cache_timeout` and `add_etags` were renamed in Flask 2.0, so this
        # raised TypeError on every download until now -- nothing ever called
        # it. See notes/plan-attachments.md.
        return send_file(
            stream,
            as_attachment=True,
            download_name=filename,
            mimetype=content_type,
            max_age=0,
            etag=False,
        )


download_view = AttachmentDownload.as_view("download")
bp.route("/<int:entity_id>/<int:object_id>/download")(download_view)


class AttachmentEdit(BaseAttachmentView, ObjectEdit):
    capability = "can_write"
    _message_success = _l("Attachment edited")


edit_view = AttachmentEdit.as_view("edit")
bp.route("/<int:entity_id>/<int:object_id>/edit")(edit_view)


class AttachmentCreateView(BaseAttachmentView, ObjectCreate):
    capability = "can_create"
    _message_success = _l("Attachment added")

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)

        self.obj.entity = self.entity
        session = sa.orm.object_session(self.entity)

        if session:
            sa.orm.session.make_transient(self.obj)

        return args, kwargs

    def breadcrumb(self):
        label = _('New attachment on "{title}"').format(title=self.entity.name)
        return nav.BreadcrumbItem(label=label)

    def get_form_buttons(self, *args, **kwargs):
        return [UPLOAD_BUTTON]


create_view = AttachmentCreateView.as_view("create")
bp.route("/<int:entity_id>/create")(create_view)


class AttachmentDelete(BaseAttachmentView, ObjectDelete):
    capability = "can_delete"


delete_view = AttachmentDelete.as_view("delete")
bp.route("/<int:entity_id>/<int:object_id>/delete")(delete_view)


class AttachmentEntity(BaseObjectView):
    """Redirects to an attachment's entity view."""

    Model = Attachment

    def get(self):
        return redirect(url_for(self.obj))


entity_view = AttachmentEntity.as_view("entity")
bp.route("/<int:object_id>/entity")(entity_view)
