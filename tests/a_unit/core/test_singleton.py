# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from abilian.core.singleton import UniqueName


class NS1(UniqueName):
    pass


class NS2(UniqueName):
    pass


def test_singleton() -> None:
    val = NS1("val")
    other_val = NS1("val")
    assert val is other_val
    assert id(val) == id(other_val)


def test_equality() -> None:
    val = NS1("val")
    assert val == "val"
    assert val == "val"


def test_namespaces() -> None:
    ns1_val = NS1("val")
    ns2_val = NS2("val")
    assert ns1_val is not ns2_val
    # equality works because of string compat
    assert ns1_val == ns2_val
