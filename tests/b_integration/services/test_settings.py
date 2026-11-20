# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import Any

import pytest
from pytest import raises

from abilian.services import settings_service
from abilian.services.settings.models import Setting, empty_value


def test_type_set() -> None:
    s = Setting()
    # registered base type: no failure
    s.type = "int"
    s.type = "bool"
    s.type = "json"
    s.type = "string"

    with raises(ValueError, match="Invalid type"):
        s.type = "dummy type name"


OBJ = [1, 2, "été", {"1": "1", "2": "2"}]


@pytest.mark.parametrize(
    ("type_", "value"),
    [
        ("int", 42),
        ("bool", True),
        ("bool", False),
        ("string", "test"),
        ("string", "bel été"),
        ("json", None),
        ("json", OBJ),
    ],
)
def test_set_get(type_: str, value: Any) -> None:
    s = Setting(key="key", type=type_)
    s.value = value
    assert s.value == value


def test_empty_value() -> None:
    s = Setting(key="key", type="json")
    assert s.value == empty_value


def test_service_facade(app, session) -> None:
    settings_service.set("key_1", 42, "int")
    session.flush()
    assert settings_service.get("key_1") == 42

    # new key with no type: raise error:
    with raises(
        ValueError, match="tried to set a new key without specifiying its type"
    ):
        settings_service.set("key_err", 42)

    # key already with type_, this should not raise an error
    settings_service.set("key_1", 24)
    session.flush()
    assert settings_service.get("key_1") == 24

    settings_service.delete("key_1")
    session.flush()
    with raises(KeyError):
        settings_service.get("key_1")

    # delete: silent by default
    settings_service.delete("non_existent")

    # delete: non-silent
    with raises(KeyError):
        settings_service.delete("non_existent", silent=False)

    # tricky use case: ask key delete, set it later, then flush
    settings_service.set("key_1", 42, "int")
    session.flush()
    settings_service.delete("key_1")
    settings_service.set("key_1", 1)
    session.flush()
    assert settings_service.get("key_1") == 1

    # list keys
    settings_service.set("key_2", 2, "int")
    settings_service.set("other", "azerty", "string")
    session.flush()
    assert sorted(settings_service.keys()) == ["key_1", "key_2", "other"]
    assert sorted(settings_service.keys(prefix="key_")) == ["key_1", "key_2"]

    # as dict
    assert settings_service.as_dict() == {"other": "azerty", "key_1": 1, "key_2": 2}
    assert settings_service.as_dict(prefix="key_") == {"key_1": 1, "key_2": 2}


def test_namespace(app, session) -> None:
    ns = settings_service.namespace("test")
    ns.set("1", 42, "int")
    session.flush()
    assert ns.get("1") == 42
    assert settings_service.get("test:1") == 42

    ns.set("sub:2", 2, "int")
    settings_service.set("other", "not in NS", "string")
    session.flush()
    assert sorted(ns.keys()) == ["1", "sub:2"]
    assert sorted(settings_service.keys()) == ["other", "test:1", "test:sub:2"]

    # sub namespace test:sub:
    sub = ns.namespace("sub")
    assert sub.keys() == ["2"]
    assert sub.get("2") == 2

    sub.set("1", 1, "int")
    session.flush()
    assert sub.get("1") == 1
    assert ns.get("1") == 42
    assert sorted(settings_service.keys()) == [
        "other",
        "test:1",
        "test:sub:1",
        "test:sub:2",
    ]

    # as dict
    assert sub.as_dict() == {"1": 1, "2": 2}
    assert ns.as_dict(prefix="sub:") == {"sub:1": 1, "sub:2": 2}
    assert ns.as_dict() == {"1": 42, "sub:1": 1, "sub:2": 2}
    assert settings_service.as_dict() == {
        "other": "not in NS",
        "test:1": 42,
        "test:sub:1": 1,
        "test:sub:2": 2,
    }

    # deletion
    sub.delete("1")
    sub.delete("2")
    session.flush()
    assert sub.keys() == []
    assert ns.keys() == ["1"]
    assert sorted(settings_service.keys()) == ["other", "test:1"]
