"""Forum views."""

from datetime import datetime
from typing import List, Union

from flask import g
from flask_babel import format_date

from abilian.i18n import _l
from abilian.sbe.apps.communities.security import is_manager
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.services.viewtracker import viewtracker


def object_viewers(entity: Union[Document, WikiPage]) -> List:
    if is_manager():
        views = viewtracker.get_views(entity=entity)
        community_members_id = [
            user.id for user in g.community.members if user.id != entity.creator.id
        ]
        viewers = []
        for view in views:
            if view.user_id in set(community_members_id):
                viewers.append(
                    {"user": view.user, "viewed_at": view.hits[-1].viewed_at}
                )
        return viewers
    return []


def activity_time_format(time: datetime, now: datetime = None) -> str:
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

    if days == 0 and hours == 0 and minutes == 0:
        return f"{seconds}{_l('s')}"

    if days == 0 and hours == 0:
        return f"{minutes}{_l('m')}"

    if days == 0:
        return f"{hours}{_l('h')}"

    if days < 30:
        return f"{days}{_l('d')}"

    if time.year == now.year:
        return f"{month_abbreviation} {time.day}"

    return f"{month_abbreviation} {str(time.year)}"
