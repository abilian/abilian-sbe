# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from flask import current_app

from abilian.core.entities import Entity
from abilian.core.models.tag import Tag
from abilian.i18n import _l
from abilian.web import url_for
from abilian.web.access_blueprint import AccessControlBlueprint
from abilian.web.views import (
    ObjectCreate,
    ObjectDelete,
    ObjectEdit,
)

from .forms import TagForm

bp = AccessControlBlueprint(
    "tags", __name__, url_prefix="/tags", template_folder="templates"
)


class BaseTagView:
    """Mixin for tag views."""

    Model = Tag
    Form = TagForm

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.extension = current_app.extensions["tags"]


class TagEdit(BaseTagView, ObjectEdit[Tag, TagForm]):
    _message_success = _l("Tag edited")


edit_view = TagEdit.as_view("edit")
bp.route("/manage/<int:object_id>/edit")(edit_view)


class TagCreate(BaseTagView, ObjectCreate[Tag, TagForm]):
    _message_success = _l("Tag created")


create_view = TagCreate.as_view("create")
bp.route("/manage/new")(create_view)


class TagDelete(BaseTagView, ObjectDelete[Tag, TagForm]):
    _message_success = _l("Tag deleted")


delete_view = TagDelete.as_view("delete")
bp.route("/manage/<int:object_id>/delete")(delete_view)

# Tags on entities
entity_bp = AccessControlBlueprint("entity_tags", __name__, url_prefix="/tags/entity")


class EntityTagEdit(ObjectEdit):
    Model = Entity

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        extension = current_app.extensions["tags"]
        self.Form = extension.entity_tags_form(self.obj)
        return args, kwargs

    def view_url(self):
        return url_for(self.obj)

    def index_url(self):
        return self.view_url()


entity_bp.route("/<int:object_id>/edit")(EntityTagEdit.as_view("edit"))
