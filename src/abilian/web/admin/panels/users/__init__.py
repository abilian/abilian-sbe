# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm
from flask import render_template
from sqlalchemy.sql.expression import func

from abilian.core.models.subjects import User
from abilian.i18n import _l
from abilian.services import get_security_service
from abilian.web.admin.panel import AdminPanel
from abilian.web.listing import Listing

from . import views

if TYPE_CHECKING:
    from collections.abc import Callable

_NAME = (func.lower(User.last_name), func.lower(User.first_name))
SORT_COLUMNS = {
    "name": _NAME,
    "email": (func.lower(User.email), *_NAME),
    "last_active": (User.last_active, *_NAME),
}


class UsersPanel(AdminPanel):
    """User administration panel."""

    id = "users"
    label = _l("Users")
    icon = "user"

    def install_additional_rules(self, add_url_rule: Callable) -> None:
        add_url_rule("/new", view_func=views.UserCreate.as_view("new"))
        add_url_rule("/<int:user_id>", view_func=views.UserEdit.as_view("user"))

    def get(self) -> str:
        security = get_security_service()
        query = User.query.options(
            sa.orm.subqueryload(User.groups), sa.orm.undefer(User.photo)
        ).filter(User.id != 0)
        listing, users = Listing.from_query(
            query,
            SORT_COLUMNS,
            "name",
            (User.first_name, User.last_name, User.email),
        )
        rows = [
            (
                user,
                [
                    role
                    for role in security.get_roles(user, no_group_roles=True)
                    if role.assignable
                ],
            )
            for user in users
        ]
        return render_template("admin/users.html", listing=listing, rows=rows)
