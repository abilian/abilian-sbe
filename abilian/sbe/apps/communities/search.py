import logging
from typing import Any, Dict, Union

import whoosh.fields as wf
import whoosh.query as wq
from flask import g
from flask_login import current_user
from whoosh.query.compound import Or
from whoosh.query.terms import Term

from abilian.sbe.app import Application

from .models import Membership

logger = logging.getLogger(__name__)

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


def init_app(app: Application) -> None:
    """Add community fields to indexing service schema."""
    indexing = app.services["indexing"]
    indexing.register_search_filter(filter_user_communities)
    indexing.register_value_provider(mark_non_community_content)

    for _name, schema in indexing.schemas.items():
        for fieldname, field in _FIELDS:
            if fieldname in schema:
                if schema[fieldname] is not field:
                    logger.warning(
                        'Field "%s" already in schema %r, replacing with '
                        "expected fieldtype instance",
                        fieldname,
                        schema,
                    )
                    del schema._fields[fieldname]
                else:
                    continue

            schema.add(fieldname, field)


def filter_user_communities() -> Union[Or, Term]:
    if g.is_manager:
        return None

    filter_q = wq.Term(_COMMUNITY_CONTENT_FIELDNAME, False)

    if not current_user.is_anonymous:
        ids = (
            Membership.query.filter(Membership.user == current_user)
            .order_by(Membership.community_id.asc())
            .values(Membership.community_id)
        )
        communities = [wq.Term("community_id", i[0]) for i in ids]

        if communities:
            communities = wq.And(
                [wq.Term(_COMMUNITY_CONTENT_FIELDNAME, True), wq.Or(communities)]
            )
            filter_q = wq.Or([filter_q, communities])

    return filter_q


def mark_non_community_content(document: Dict[str, Any], obj: Any) -> Dict[str, Any]:
    if _COMMUNITY_CONTENT_FIELDNAME not in document:
        document[_COMMUNITY_CONTENT_FIELDNAME] = getattr(
            obj, _COMMUNITY_CONTENT_FIELDNAME, False
        )

    return document
