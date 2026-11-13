# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm
from flask import current_app
from flask_login import current_user
from werkzeug.exceptions import BadRequest, Forbidden

from abilian.core.entities import Entity
from abilian.core.models.comment import Comment, is_commentable
from abilian.core.util import utc_dt
from abilian.i18n import _, _l
from abilian.web import nav, url_for
from abilian.web.access_blueprint import AccessControlBlueprint
from abilian.web.action import ButtonAction, actions
from abilian.web.views.object import (
    CANCEL_BUTTON,
    ObjectCreate,
    ObjectDelete,
    ObjectEdit,
)

from .forms import CommentForm

if TYPE_CHECKING:
    from flask.blueprints import BlueprintSetupState

bp = AccessControlBlueprint("comments", __name__, url_prefix="/comments")


def _default_comment_view(obj, obj_type, obj_id, **kwargs):
    entity = obj.entity
    return url_for(entity, _anchor=f"comment-{obj.id}")


@bp.record_once
def register_default_view(state: BlueprintSetupState) -> None:
    state.app.default_view.register(Comment, _default_comment_view)


COMMENT_BUTTON = ButtonAction("form", "edit", btn_class="primary", title=_l("Post"))


class BaseCommentView:
    Model = Comment
    Form = CommentForm

    #: commented entity
    entity: Entity | None = None

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        entity_id = kwargs.pop("entity_id", None)
        if entity_id is not None:
            self.entity = Entity.query.get(entity_id)

        if self.entity is None:
            msg = "No entity to comment"
            raise BadRequest(msg)

        if not is_commentable(self.entity):
            msg = "This entity is not commentable"
            raise BadRequest(msg)

        # Nothing used to check anything here. The rule was written twice in
        # `macros/comment.html` and nowhere else, so every route was open to
        # any authenticated user -- unreachable only because no model is
        # registered commentable. See notes/plan-attachments.md.
        if not self.has_capability(current_app.extensions["comments"]):
            raise Forbidden

        actions.context["object"] = self.entity
        return args, kwargs

    def has_capability(self, comments) -> bool:
        """The capability this view needs, asked of the comments extension.

        Reading is about the commented entity; editing and deleting are about
        the comment, because their rule includes its author.
        """
        return comments.can_read(self.entity)

    def view_url(self):
        kw = {}
        if self.obj and self.obj.id:
            kw["_anchor"] = f"comment-{self.obj.id}"
        return url_for(self.entity, **kw)

    def index_url(self):
        return self.view_url()

    @property
    def activity_target(self):
        return self.entity


class CommentEditView(BaseCommentView, ObjectEdit):
    _message_success = _l("Comment edited")

    def has_capability(self, comments) -> bool:
        return comments.can_write(self.obj)

    def breadcrumb(self):
        label = _('Edit comment on "{title}"').format(title=self.entity.name)
        return nav.BreadcrumbItem(label=label)

    def get_form_buttons(self, *args, **kwargs):
        return [COMMENT_BUTTON, CANCEL_BUTTON]

    def after_populate_obj(self) -> None:
        obj_meta = self.obj.meta.setdefault("abilian.core.models.comment", {})
        history = obj_meta.setdefault("history", [])
        history.append(
            {
                "user_id": current_user.id,
                "user": str(current_user),
                "date": utc_dt(datetime.utcnow()).isoformat(),
            }
        )
        self.obj.meta.changed()


edit_view = CommentEditView.as_view("edit")
bp.route("/<int:entity_id>/<int:object_id>/edit")(edit_view)


class CommentCreateView(BaseCommentView, ObjectCreate):
    """"""

    _message_success = _l("Comment added")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def has_capability(self, comments) -> bool:
        return comments.can_create(self.entity)

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        self.obj.entity = self.entity
        session = sa.orm.object_session(self.entity)

        if session:
            sa.orm.session.make_transient(self.obj)

        return args, kwargs

    def breadcrumb(self):
        label = _('New comment on "{title}"').format(title=self.entity.name)
        return nav.BreadcrumbItem(label=label)

    def get_form_buttons(self, *args, **kwargs):
        return [COMMENT_BUTTON, CANCEL_BUTTON]


create_view = CommentCreateView.as_view("create")
bp.route("/<int:entity_id>/create")(create_view)


class CommentDeleteView(BaseCommentView, ObjectDelete):
    _message_success = _l("Comment deleted")

    def has_capability(self, comments) -> bool:
        return comments.can_delete(self.obj)


delete_view = CommentDeleteView.as_view("delete")
bp.route("/<int:entity_id>/<int:object_id>/delete")(delete_view)
