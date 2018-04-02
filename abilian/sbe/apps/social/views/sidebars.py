"""Provides content for sidebars, accessible via the 'g' object.

TODO: make it smarter (direct access from 'g' using lazy objects?) and
cacheable.
"""

from __future__ import absolute_import, print_function, unicode_literals

from datetime import datetime, timedelta

from abilian.core.models.subjects import User
from flask import g
from flask_login import current_user

from abilian.sbe.apps.communities.models import Community, Membership

from .social import social


class Sidebars(object):
    @property
    def latest_visitors(self):
        return User.query.filter(User.last_active != None) \
            .order_by(User.last_active.desc()) \
            .limit(15) \
            .all()

    @property
    def active_visitor_count(self):
        one_minute_ago = (datetime.utcnow() - timedelta(0, 60))
        return User.query.filter(User.last_active > one_minute_ago).count()

    @property
    def my_communities(self):
        query = Community.query
        query = query.order_by(Community.last_active_at.desc())
        if not current_user.has_role('admin'):
            # Filter with permissions
            query = query.join(Membership) \
                .filter(Membership.user == current_user)
        return query.limit(10).all()

    @property
    def all_communities(self):
        # TODO: limit
        return []
        # return Community.query.all()


@social.before_request
def inject_sidebars():
    g.sidebars = Sidebars()
