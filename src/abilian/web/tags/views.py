# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from flask import current_app
from flask_login import current_user
from werkzeug.exceptions import Forbidden

from abilian.core.entities import Entity
from abilian.core.util import unwrap
from abilian.services.security import AUTHENTICATED
from abilian.web import url_for
from abilian.web.access_blueprint import AccessControlBlueprint
from abilian.web.views import ObjectEdit

#: No views of its own: it carries the templates of the admin tags panel.
bp = AccessControlBlueprint(
    "tags", __name__, url_prefix="/tags", template_folder="templates"
)

entity_bp = AccessControlBlueprint(
    "entity_tags", __name__, url_prefix="/tags/entity", allowed_roles=AUTHENTICATED
)


class EntityTagEdit(ObjectEdit):
    Model = Entity

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        extension = current_app.extensions["tags"]
        if not extension.can_edit(unwrap(current_user), self.obj):
            raise Forbidden
        self.Form = extension.entity_tags_form(self.obj)
        return args, kwargs

    def view_url(self):
        return url_for(self.obj)

    def index_url(self):
        return self.view_url()


entity_bp.route("/<int:object_id>/edit")(EntityTagEdit.as_view("edit"))
