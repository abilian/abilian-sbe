# coding=utf-8
"""
Forum views
"""

from flask import g
from flask_login import current_user
from abilian.services.security import Manager, Admin

from abilian.services.viewtracker import viewtracker


def is_manager(user,community):
    if community.has_permission(user, Manager):
        if user in community.members or user == community.creator:
            return True

    if community.has_permission(user, Admin):
        return True

    return False


def object_viewers(entity):
    if is_manager(current_user,g.community):
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
