"""
Provides content for sidebars, accessible via the 'g' object.

TODO: make it smarter (direct access from 'g' using lazy objects?) and
cacheable.
"""

from datetime import datetime, timedelta
from flask import g

from abilian.core.models.subjects import User
from abilian.sbe.apps.social.views.social import social


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
    return User.query.filter(
      User.last_active > one_minute_ago).count()

  @property
  def my_communities(self):
    return []
    # TODO: filter by permission
    # TODO: limit
    #return Community.query.all()

  @property
  def all_communities(self):
    # TODO: limit
    return []
    #return Community.query.all()


@social.before_request
def inject_sidebars():
  g.sidebars = Sidebars()
