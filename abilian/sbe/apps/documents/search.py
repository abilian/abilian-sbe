# coding=utf-8
"""
Indexing related utilities for Folder, Documents
"""
from __future__ import absolute_import

import sqlalchemy as sa
from flask import current_app

from abilian.core.entities import Entity

from .models import CmisObject


def reindex_tree(obj):
    """
    Schedule reindexing `obj` and all of its descendants.

    Generally needed to update indexed security.
    """
    assert isinstance(obj, CmisObject)

    svc = current_app.services['indexing']
    if not svc.running:
        return

    descendants = sa.select([CmisObject.id, CmisObject._parent_id]) \
        .where(CmisObject._parent_id == sa.bindparam('ancestor_id')) \
        .cte(name='descendants', recursive=True)
    da = descendants.alias()
    CA = sa.orm.aliased(CmisObject)
    d_ids = sa.select([CA.id, CA._parent_id])
    descendants = descendants.union_all(d_ids.where(CA._parent_id == da.c.id))
    session = sa.orm.object_session(obj) or current_app.db.session()

    # including ancestor_id in entity_ids_q will garantee at least 1 value for the
    # "IN" predicate; otherwise when using sqlite (as during tests...)
    # 'ResourceClosedError' will be raised.
    #
    # as an added bonus, "obj" will also be in query results, thus will be added
    # in "to_update" without needing to do it apart.
    entity_ids_q = sa.union(
        sa.select([descendants.c.id]), sa.select([sa.bindparam('ancestor_id')]))
    q = session.query(Entity) \
        .filter(Entity.id.in_(entity_ids_q)) \
        .options(sa.orm.noload('*')) \
        .params(ancestor_id=obj.id)

    to_update = svc.app_state.to_update
    key = 'changed'

    for item in q.yield_per(1000):
        to_update.append((key, item))
