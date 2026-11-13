# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import whoosh.fields as wf
import whoosh.query as wq
from loguru import logger

from abilian.services import get_service

from .models import Membership

if TYPE_CHECKING:
    from flask import Flask
    from whoosh.query.compound import Or
    from whoosh.query.terms import Term

    from abilian.core.models.subjects import User
    from abilian.services.indexing.service import IndexService

_COMMUNITY_CONTENT_FIELDNAME = "is_community_content"
_COMMUNITY_CONTENT_FIELD = wf.BOOLEAN()

_COMMUNITY_ID_FIELD = wf.NUMERIC(
    numtype=int, bits=64, signed=False, stored=True, unique=False
)
_COMMUNITY_SLUG_FIELD = wf.ID(stored=True)

_FIELDS = [
    (_COMMUNITY_CONTENT_FIELDNAME, _COMMUNITY_CONTENT_FIELD),
    ("community_id", _COMMUNITY_ID_FIELD),
    ("community_slug", _COMMUNITY_SLUG_FIELD),
]


def init_app(app: Flask) -> None:
    """Add community fields to indexing service schema."""
    indexing = cast("IndexService", get_service("indexing"))
    indexing.register_search_filter(filter_user_communities)
    indexing.register_value_provider(mark_non_community_content)

    for schema in indexing.schemas.values():
        for fieldname, field in _FIELDS:
            if fieldname in schema:
                if schema[fieldname] is not field:
                    logger.warning(
                        "Field {fieldname} already in schema {schema}, replacing with "
                        "expected fieldtype instance",
                        fieldname=repr(fieldname),
                        schema=repr(schema),
                    )
                    del schema._fields[fieldname]
                else:
                    continue

            schema.add(fieldname, field)


def filter_user_communities(user: User) -> Or | Term:
    """Community content is visible to that community's members.

    Takes its subject rather than reaching for one: it used to read
    `current_user` and `g.is_manager`, so it could not run outside a request,
    and the `g` read was the second place deciding "may this user see
    everything anyway" -- `IndexService.search` settles that now, before this is
    called.
    """
    filter_q = wq.Term(_COMMUNITY_CONTENT_FIELDNAME, False)

    if not user.is_anonymous:
        ids = (
            Membership.query.filter(Membership.user == user)
            .order_by(Membership.community_id.asc())
            .with_entities(Membership.community_id)
        )
        communities = [wq.Term("community_id", i[0]) for i in ids]

        if communities:
            communities = wq.And(
                [
                    wq.Term(_COMMUNITY_CONTENT_FIELDNAME, True),
                    wq.Or(communities),
                ]
            )
            filter_q = wq.Or([filter_q, communities])

    return filter_q


def mark_non_community_content(document: dict[str, Any], obj: Any) -> dict[str, Any]:
    if _COMMUNITY_CONTENT_FIELDNAME not in document:
        document[_COMMUNITY_CONTENT_FIELDNAME] = getattr(
            obj, _COMMUNITY_CONTENT_FIELDNAME, False
        )

    return document
