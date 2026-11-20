# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm
from flask import render_template
from sqlalchemy.sql.expression import func

from abilian.core.models.subjects import Group
from abilian.i18n import _l
from abilian.services import get_security_service
from abilian.web.admin.panel import AdminPanel
from abilian.web.listing import Listing

from . import views

if TYPE_CHECKING:
    from collections.abc import Callable


class GroupsPanel(AdminPanel):
    """Group administration panel."""

    id = "groups"
    label = _l("Groups")
    icon = "th"

    def install_additional_rules(self, add_url_rule: Callable) -> None:
        add_url_rule("/new", view_func=views.GroupCreate.as_view("new"))
        add_url_rule("/<int:group_id>/", view_func=views.GroupView.as_view("group"))
        add_url_rule(
            "/<int:group_id>/edit",
            view_func=views.GroupEdit.as_view(
                "group_edit", view_endpoint=".groups_group"
            ),
        )

    def get(self) -> str:
        security = get_security_service()
        query = Group.query.options(sa.orm.noload("*")).add_columns(Group.members_count)
        listing, groups = Listing.from_query(
            query,
            {"name": (func.lower(Group.name),)},
            "name",
            (Group.name,),
        )
        rows = [
            (
                group,
                members_count or 0,
                [role for role in security.get_roles(group) if role.assignable],
            )
            for group, members_count in groups
        ]
        return render_template("admin/groups.html", listing=listing, rows=rows)
