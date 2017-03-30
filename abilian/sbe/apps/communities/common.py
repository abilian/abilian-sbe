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
            community_members_dict = {user.id:user for user in g.community.members if user.id != obj.creator.id}
            viewers = []
            for view in tracked_views:
                if view.user_id in set(community_members_dict.keys()):
                    viewers.append({'user':community_members_dict[view.user_id],'viewed_at':view.viewed_at})
            return viewers
