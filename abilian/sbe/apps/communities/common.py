# coding=utf-8
"""
Forum views
"""

from datetime import datetime

from flask import current_app, g
from flask_babel import format_date
from flask_login import current_user

from abilian.i18n import _l
from abilian.sbe.apps.communities.security import is_manager
from abilian.services.viewtracker import viewtracker


def object_viewers(entity):
    if is_manager():
        views = viewtracker.get_views(entity=entity)
        community_members_id = [
            user.id for user in g.community.members
            if user.id != entity.creator.id
        ]
        viewers = []
        for view in views:
            if view.user_id in set(community_members_id):
                viewers.append({
                    'user': view.user,
                    'viewed_at': view.hits[-1].viewed_at
                })
        return viewers


def activity_time_format(time):
    if not time:
        return ""

    current_date = datetime.utcnow()
    time_diffrence = current_date - time
    month_abbreviation = format_date(time, "MMM")
    days, hours, minutes, seconds = time_diffrence.days, time_diffrence.seconds // 3600, time_diffrence.seconds // 60, time_diffrence.seconds

    if days == 0:
        if minutes < 1:
            return u"{}{}".format(seconds, _l(u"s"))
        if minutes < 60:
            return u"{}{}".format(minutes % 60, _l(u"m"))
        return u"{}{}".format(hours, _l(u"h"))

    if days < 30:
        return u"{}{}".format(days, _l(u"d"))

    if time.year == current_date.year:
        return u"{} {}".format(month_abbreviation, time.day)

    return u"{} {}".format(month_abbreviation, str(time.year))
