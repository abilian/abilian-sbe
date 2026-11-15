# Copyright (c) 2012-2024, Abilian SAS

"""Forum views."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import g
from flask_babel import format_date

from abilian.i18n import _l
from abilian.sbe.apps.communities.security import can_manage
from abilian.services.viewtracker import viewtracker
from abilian.services.viewtracker.models import Hit

if TYPE_CHECKING:
    from abilian.sbe.apps.documents.models import Document
    from abilian.sbe.apps.wiki.models import WikiPage


def object_viewers(entity: Document | WikiPage) -> list:
    if can_manage(g.community):
        views = viewtracker.get_views(entity=entity)
        community_members_id = [
            user.id for user in g.community.members if user.id != entity.creator.id
        ]
        viewers = []
        for view in views:
            if view.user_id in set(community_members_id):
                viewers.append(
                    {
                        "user": view.user,
                        # order_by(None): the relationship's ORDER BY has no
                        # place in an aggregate, and PostgreSQL refuses it.
                        "viewed_at": view.hits.order_by(None)
                        .with_entities(sa.func.max(Hit.viewed_at))
                        .scalar(),
                    }
                )
        return viewers
    return []


def activity_time_format(time: datetime, now: datetime | None = None) -> str:
    if not time:
        return ""

    if not now:
        now = datetime.utcnow()
    time_delta = now - time
    month_abbreviation = format_date(time, "MMM")
    days, hours, minutes, seconds = (
        time_delta.days,
        time_delta.seconds // 3600,
        time_delta.seconds // 60,
        time_delta.seconds,
    )

    match days:
        case 0 if hours == 0 and minutes == 0:
            return f"{seconds}{_l('s')}"

        case 0 if hours == 0:
            return f"{minutes}{_l('m')}"

        case 0:
            return f"{hours}{_l('h')}"

    if days < 30:
        return f"{days}{_l('d')}"

    if time.year == now.year:
        return f"{month_abbreviation} {time.day}"

    return f"{month_abbreviation} {time.year!s}"
