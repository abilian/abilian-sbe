# coding=utf-8
"""
Forum views
"""

from flask import g
from flask_login import current_user

from flask import current_app
from abilian.services.viewtracker import viewtracker
from abilian.sbe.apps.communities.security import is_manager


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
