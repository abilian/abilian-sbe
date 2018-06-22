# coding=utf-8
"""Forum views."""

from __future__ import absolute_import, print_function, unicode_literals

from datetime import datetime

from abilian.i18n import _l
from abilian.services.viewtracker import viewtracker
from flask import g
from flask_babel import format_date

from abilian.sbe.apps.communities.security import is_manager


def object_viewers(entity):
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


def activity_time_format(time, now=None):
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
        return "{}{}".format(seconds, _l("s"))

    if days == 0 and hours == 0:
        return "{}{}".format(minutes, _l("m"))

    if days == 0:
        return "{}{}".format(hours, _l("h"))

    if days < 30:
        return "{}{}".format(days, _l("d"))

    if time.year == now.year:
        return "{} {}".format(month_abbreviation, time.day)

    return "{} {}".format(month_abbreviation, str(time.year))
