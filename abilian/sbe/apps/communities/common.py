# coding=utf-8
"""
Forum views
"""

from flask_login import current_user
from flask import current_app, g
from abilian.services.activitytracker import activitytracker


def object_viewers(obj):
    if current_user.has_role('manager'):
        tracked_views = activitytracker.get_viewers(obj.id)
        community_members_id = [user.id for user in g.community.members if user.id != obj.creator.id]
        viewers = []
        for view in tracked_views:
            if view.user_id in set(community_members_id):
                viewers.append({'user':view.user,'viewed_at':view.track_logs[-1].viewed_at})
        return viewers
