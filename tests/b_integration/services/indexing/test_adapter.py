# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from whoosh.fields import NUMERIC, TEXT, Schema

from abilian.core.entities import Entity
from abilian.core.models.base import (
    SEARCHABLE,
    IdMixin,
    Indexable as CoreIndexable,
    Model,
)
from abilian.services.indexing.adapter import SAAdapter
from tests.util import class_fqn


class SANotAdaptable:
    pass


class SANotIndexable(IdMixin, Model):
    __tablename__ = "sa_not_indexable"
    __indexable__ = False


class Indexable(IdMixin, CoreIndexable, Model):
    __tablename__ = "sa_indexable"
    __index_to__ = (("related.name", ("name", "text")), ("related.description", "text"))

    num = sa.Column(sa.Integer, info=SEARCHABLE | {"index_to": (("num", NUMERIC()),)})


class SubclassEntityIndexable(Entity):
    pass


def test_can_adapt() -> None:
    assert not SAAdapter.can_adapt(SANotAdaptable)
    assert SAAdapter.can_adapt(SANotIndexable)
    assert SAAdapter.can_adapt(Indexable)
    assert SAAdapter.can_adapt(Entity)


def test_build_attrs_1() -> None:
    schema = Schema()
    adapter = SAAdapter(SANotIndexable, schema)
    assert not adapter.indexable
    assert adapter.doc_attrs == {}


def test_build_attrs_2() -> None:
    schema = Schema()
    adapter = SAAdapter(Entity, schema)
    assert adapter.indexable == False


def test_build_attrs_3() -> None:
    schema = Schema()
    adapter = SAAdapter(SubclassEntityIndexable, schema)
    assert adapter.indexable
    assert set(adapter.doc_attrs) == {
        "allowed_roles_and_users",
        "created_at",
        "creator",
        "creator_name",
        "id",
        "name",
        "name_prefix",
        "object_key",
        "object_type",
        "owner",
        "owner_name",
        "slug",
        "tag_ids",
        "tag_text",
        "text",
        "updated_at",
    }

    # FIXME: this test doesn't make sense
    # assert all(lambda f: callable(f) for f in adapter.doc_attrs.values())

    assert set(schema.names()) == {
        "allowed_roles_and_users",
        "created_at",
        "creator",
        "creator_name",
        "id",
        "name",
        "name_prefix",
        "object_key",
        "object_type",
        "owner",
        "owner_name",
        "slug",
        "tag_ids",
        "tag_text",
        "text",
        "updated_at",
    }


def test_build_attrs_4() -> None:
    schema = Schema(id=NUMERIC(bits=64, signed=False, stored=True, unique=True))
    adapter = SAAdapter(Indexable, schema)
    assert adapter.indexable
    assert set(adapter.doc_attrs) == {
        "id",
        "text",
        "num",
        "name",
        "object_type",
        "object_key",
    }

    # FIXME: this test doesn't make sense
    # assert all(lambda f: callable(f) for f in adapter.doc_attrs.values())

    assert set(schema.names()) == {
        "id",
        "text",
        "num",
        "name",
        "object_type",
        "object_key",
    }
    assert isinstance(schema["text"], TEXT)
    assert isinstance(schema["num"], NUMERIC)


def test_get_document(app, db) -> None:
    schema = Schema()
    adapter = SAAdapter(SubclassEntityIndexable, schema)
    expected = {
        "id": 2,
        "name": "entity name",
        "created_at": datetime(2013, 11, 28, 16, 17, 0),
        "updated_at": datetime(2013, 11, 29, 12, 17, 58),
    }
    obj = SubclassEntityIndexable(**expected)
    obj.slug = "entity-name"

    expected["object_type"] = class_fqn(SubclassEntityIndexable)
    expected["object_key"] = f"{class_fqn(SubclassEntityIndexable)}:2"
    expected["text"] = "entity name"
    expected["slug"] = "entity-name"
    expected["name_prefix"] = "entity name"
    expected["allowed_roles_and_users"] = "role:admin"

    with app.test_request_context():
        assert adapter.get_document(obj) == expected


def test_get_document_with_schema() -> None:
    # test retrieve related attributes
    schema = Schema(id=NUMERIC(bits=64, signed=False, stored=True, unique=True))
    adapter = SAAdapter(Indexable, schema)
    expected: dict[str, Any] = {"id": 1, "num": 42}
    obj = Indexable(**expected)
    obj.related = type("Related", (object,), {"name": None})()
    expected["name"] = obj.related.name = "related name"
    obj.related.description = "description text"
    expected["text"] = f"{obj.related.name} {obj.related.description}"
    doc = adapter.get_document(obj)

    assert set(doc) == {"id", "name", "num", "text", "object_type", "object_key"}
    assert doc["id"] == 1
    assert doc["num"] == 42
    assert doc["name"] == "related name"
    assert "related name" in doc["text"]
    assert "description text" in doc["text"]
