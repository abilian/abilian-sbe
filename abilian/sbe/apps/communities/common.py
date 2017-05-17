# coding=utf-8
"""
Forum views
"""

from flask import current_app, g
from flask_login import current_user
from datetime import datetime

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
    current_date = datetime.utcnow()
    time_diffrence = current_date - time
    month_abbreviation = time.strftime('%B')[:3]
    days, hours, minutes, seconds = time_diffrence.days, time_diffrence.seconds // 3600, time_diffrence.seconds // 60, time_diffrence.seconds

    if time.year == current_date.year:
        if time.month == current_date.month:
            if time.day == current_date.day:
                if minutes < 1:
                    return "{}s".format(seconds)
                elif minutes > 60:
                    return "{}h".format(hours)
                else:
                    return "{}m".format(minutes % 60)
            elif days == 0:
                return "{}h".format(hours)
            else:
                return "{}d".format(days)
        else:
            return "{} {}".format(month_abbreviation, time.day)
    else:
        return "{} {}".format(month_abbreviation, str(time.year))
