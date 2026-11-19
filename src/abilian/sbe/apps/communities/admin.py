# Copyright (c) 2026, Abilian SAS

"""The communities, in the site's administration."""

from __future__ import annotations

from flask import render_template
from sqlalchemy.sql.expression import func

from abilian.i18n import _l
from abilian.web.admin.panel import AdminPanel
from abilian.web.listing import Listing

from .models import Community, managers_of

_NAME = (func.lower(Community.name),)
SORT_COLUMNS = {
    "name": _NAME,
    "members": (Community.membership_count, *_NAME),
    "documents": (Community.document_count, *_NAME),
    "last_active": (Community.last_active_at, *_NAME),
}


class CommunitiesPanel(AdminPanel):
    """Every community, whoever is in it: its managers, its size, its activity."""

    id = "communities"
    label = _l("Communities")
    icon = "users"

    def get(self) -> str:
        listing, communities = Listing.from_query(
            Community.query, SORT_COLUMNS, "name", (Community.name,)
        )
        return render_template(
            "admin/communities.html",
            listing=listing,
            communities=communities,
            managers=managers_of(communities),
        )
