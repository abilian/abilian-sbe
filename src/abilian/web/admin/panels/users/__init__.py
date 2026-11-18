# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm
from flask import render_template, request
from sqlalchemy.sql.expression import func

from abilian.core.extensions import db
from abilian.core.models.subjects import User
from abilian.i18n import _l
from abilian.services.security.models import ADMIN, RoleAssignment
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
        add_url_rule(
            "/<int:user_id>/account",
            "account",
            view_func=views.account_action,
            methods=["POST"],
        )

    def get(self) -> str:
        admin_ids = sa.select(RoleAssignment.user_id).where(
            RoleAssignment.role == ADMIN, RoleAssignment.object_id.is_(None)
        )
        everyone = User.query.filter(User.id != 0)
        kinds = {
            "all": everyone,
            "invited": everyone.filter(User.can_login, User.last_active.is_(None)),
            "disabled": everyone.filter(sa.not_(User.can_login)),
            "admins": everyone.filter(User.id.in_(admin_ids)),
        }
        kind = request.args.get("state", "all")
        if kind not in kinds:
            kind = "all"
        query = kinds[kind].options(sa.orm.undefer(User.photo))
        listing, users = Listing.from_query(
            query,
            SORT_COLUMNS,
            "name",
            (User.first_name, User.last_name, User.email),
        )
        admins = set(db.session.scalars(admin_ids))
        rows = [(user, [ADMIN] if user.id in admins else []) for user in users]
        counts = {name: query.count() for name, query in kinds.items()}
        return render_template(
            "admin/users.html", listing=listing, rows=rows, kind=kind, counts=counts
        )
