# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column

from abilian.core.entities import Entity
from abilian.core.sqlalchemy import UUID, JSONDict, JSONList

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class DummyModel2(Entity):
    list_attr = Column(JSONList())
    dict_attr = Column(JSONDict())
    uuid = Column(UUID())


def test_list_attribute(session: Session) -> None:
    model = DummyModel2(list_attr=[1, 2, 3])
    session.add(model)
    session.commit()
    model_id = model.id
    session.remove()
    model2 = DummyModel2.query.get(model_id)
    assert model2.list_attr == [1, 2, 3]

    model2.list_attr.append(4)
    assert model2.list_attr == [1, 2, 3, 4]

    del model2.list_attr[0]
    assert model2.list_attr == [2, 3, 4]


def test_dict_attribute(session: Session) -> None:
    model = DummyModel2(dict_attr={"a": 3, "b": 4})
    session.add(model)
    session.commit()
    model_id = model.id
    session.remove()
    model2 = DummyModel2.query.get(model_id)
    assert model2.dict_attr == {"a": 3, "b": 4}

    model2.dict_attr["c"] = 5
    assert model2.dict_attr == {"a": 3, "b": 4, "c": 5}


def test_uuid_attribute(session: Session) -> None:
    # uuid from string
    model = DummyModel2(uuid="c5ad316a-2cd0-4f78-a49b-cff216c10713")
    session.add(model)
    session.commit()
    model_id = model.id
    session.remove()
    model2 = DummyModel2.query.get(model_id)

    assert isinstance(model2.uuid, uuid.UUID)

    # plain UUID object
    u = uuid.UUID("3eb7f164-bf15-4564-a058-31bdea0196e6")
    model = DummyModel2(uuid=u)
    session.add(model)
    session.commit()
    model_id = model.id
    session.remove()
    model2 = DummyModel2.query.get(model_id)

    assert isinstance(model2.uuid, uuid.UUID)
    assert model2.uuid == u
