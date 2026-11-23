# Copyright (c) 2026, Abilian SAS

"""A computed column, an SQL expression mapped on a model, is no column of its
table: indexing and audit read an `info` it does not have, and the application
failed to start."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import column_property
from whoosh.fields import Schema

from abilian.core.entities import Entity
from abilian.core.models.base import SEARCHABLE
from abilian.services import audit_service
from abilian.services.indexing.adapter import SAAdapter

if TYPE_CHECKING:
    from abilian.core.sqlalchemy import SQLAlchemy


class TitledContent(Entity):
    title = sa.Column(sa.UnicodeText, info=SEARCHABLE)


TitledContent.has_title = column_property(TitledContent.__table__.c.title.is_not(None))


def test_indexing_leaves_a_computed_column_out() -> None:
    adapter = SAAdapter(TitledContent, Schema())

    assert "title" in adapter.doc_attrs
    assert "has_title" not in adapter.doc_attrs


def test_audit_leaves_a_computed_column_out(db: SQLAlchemy) -> None:
    audit_service.start()
    try:
        audited = {attr.key for attr in TitledContent.__auditable__.audited_attrs}
    finally:
        audit_service.stop()

    assert "title" in audited
    assert "has_title" not in audited
