# coding=utf-8
"""
"""
from __future__ import absolute_import

from flask import g
from flask.ext.login import current_user
import whoosh.query as wq
import whoosh.fields as wf

from .models import Membership


_COMMUNITY_CONTENT_FIELDNAME = 'is_community_content'
_COMMUNITY_CONTENT_FIELD = wf.BOOLEAN()

def init_app(app):
  """
  Add community fields to indexing service schema
  """
  indexing = app.services['indexing']
  indexing.register_search_filter(filter_user_communities)
  indexing.register_value_provider(mark_non_community_content)

  for name, schema in indexing.schemas.items():
    if _COMMUNITY_CONTENT_FIELDNAME not in schema:
      schema.add(_COMMUNITY_CONTENT_FIELDNAME,
                 _COMMUNITY_CONTENT_FIELD)


def filter_user_communities():
  if g.is_manager:
    return None

  filter_q = wq.Term(_COMMUNITY_CONTENT_FIELDNAME, False)

  if not current_user.is_anonymous():
    ids = Membership.query\
        .filter(Membership.user == current_user)\
        .order_by(Membership.community_id.asc())\
        .values(Membership.community_id)
    communities = [wq.Term('community_id', i[0]) for i in ids]

    if communities:
      communities = wq.And(
        [wq.Term(_COMMUNITY_CONTENT_FIELDNAME, True),
         wq.Or(communities)])
      filter_q = wq.Or([filter_q, communities])

  return filter_q


def mark_non_community_content(document, obj):
  if _COMMUNITY_CONTENT_FIELDNAME not in document:
    document[_COMMUNITY_CONTENT_FIELDNAME] = \
        getattr(obj, _COMMUNITY_CONTENT_FIELDNAME, False)

  return document
