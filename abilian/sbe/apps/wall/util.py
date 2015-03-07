"""
Some functions to retrieve activity entries.

"""
# TODO: move to the activity service ?

from flask import g, abort, current_app
from flask.ext.login import current_user
import sqlalchemy as sa

from abilian.core.extensions import db
from abilian.services.activity import ActivityEntry

from abilian.sbe.apps.communities.models import Membership
from abilian.sbe.apps.documents.models import Folder, Document


def get_recent_entries(num=20, user=None, community=None):
  AE = ActivityEntry

  # Check just in case
  if not current_user.has_role('admin'):
    if community and not community.has_member(current_user):
      abort(403)

  query = AE.query.options(sa.orm.joinedload(AE.object))

  if community:
    query = query.filter(sa.or_(AE.target == g.community,
                                AE.object == g.community))
  if user:
    query = query.filter(AE.actor == user)

  # Security check
  #
  # we use communities ids instead of object because as of sqlalchemy 0.8 the
  # 'in_' operator cannot use with relationships, only foreign keys values
  if not community and not current_user.has_role('admin'):
    M = Membership
    communities = M.query\
      .filter(M.user_id == current_user.id)\
      .values(M.community_id)

    if not communities:
      return []

    query = query.filter(sa.or_(AE.target_id.in_(communities),
                                AE.object_id.in_(communities)))

  query = query.order_by(AE.happened_at.desc()).limit(1000)
  limit = min(num * 2, 100)  # get twice entries as needed, but ceil to 100
  entries = []
  deleted = False
  security = current_app.services['security']

  for entry in query.yield_per(limit):
    if len(entries) >= num:
      break

    # Remove entries corresponding to deleted objects
    if entry.object is None:
      db.session.delete(entry)
      deleted = True
      continue

    if (isinstance(entry.object, (Folder, Document))
        and not security.has_role(current_user, 'reader', entry.object)):
        continue

    entries.append(entry)

  if deleted:
    db.session.commit()

  return entries
