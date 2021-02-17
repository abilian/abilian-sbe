"""Indexing related utilities for Folder, Documents."""
import sqlalchemy as sa

from abilian.core.entities import Entity
from abilian.core.extensions import db
from abilian.sbe.apps.documents.models import Folder
from abilian.services import get_service

from .models import CmisObject


def reindex_tree(obj: Folder) -> None:
    """Schedule reindexing `obj` and all of its descendants.

    Generally needed to update indexed security.
    """
    assert isinstance(obj, CmisObject)

    index_service = get_service("indexing")
    if not index_service.running:
        return

    descendants = (
        sa.select([CmisObject.id, CmisObject._parent_id])
        .where(CmisObject._parent_id == sa.bindparam("ancestor_id"))
        .cte(name="descendants", recursive=True)
    )
    da = descendants.alias()
    CA = sa.orm.aliased(CmisObject)
    d_ids = sa.select([CA.id, CA._parent_id])
    descendants = descendants.union_all(d_ids.where(CA._parent_id == da.c.id))
    session = sa.orm.object_session(obj) or db.session()

    # including ancestor_id in entity_ids_q will garantee at least 1 value for the
    # "IN" predicate; otherwise when using sqlite (as during tests...)
    # 'ResourceClosedError' will be raised.
    #
    # as an added bonus, "obj" will also be in query results, thus will be added
    # in "to_update" without needing to do it apart.
    entity_ids_q = sa.union(
        sa.select([descendants.c.id]), sa.select([sa.bindparam("ancestor_id")])
    )
    query = (
        session.query(Entity)
        .filter(Entity.id.in_(entity_ids_q))
        .options(sa.orm.noload("*"))
        .params(ancestor_id=obj.id)
    )

    to_update = index_service.app_state.to_update
    key = "changed"

    for item in query.yield_per(1000):
        to_update.append((key, item))
