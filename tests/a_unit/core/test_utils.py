# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from abilian.core.util import Pagination, slugify


def test_pagination_1() -> None:
    p = Pagination(1, 10, 10)
    pages = list(p.iter_pages())
    assert pages == [1]
    assert not p.has_prev
    assert not p.has_next
    assert p.prev is None
    assert p.next is None


def test_pagination_2() -> None:
    p = Pagination(1, 10, 20)
    pages = list(p.iter_pages())
    assert pages == [1, 2]
    assert not p.has_prev
    assert p.has_next
    assert p.prev is None
    assert p.next == 2


def test_pagination_3() -> None:
    p = Pagination(1, 10, 100)
    pages = list(p.iter_pages())
    assert pages == [1, 2, 3, 4, 5, None, 9, 10]
    assert not p.has_prev
    assert p.has_next
    assert p.prev is None
    assert p.next == 2


def test_pagination_4() -> None:
    p = Pagination(10, 10, 100)
    pages = list(p.iter_pages())
    assert pages == [1, 2, None, 8, 9, 10]
    assert p.has_prev
    assert not p.has_next
    assert p.prev == 9
    assert p.next is None


def test_slugify_basic() -> None:
    slug = slugify("a b c")
    assert slug == "a-b-c"
    assert isinstance(slug, str)
    assert slugify(slug) == "a-b-c"  # idempotent


def test_slugify_separator() -> None:
    slug = slugify("a-b++ c-+", "+")
    assert slug == "a+b+c"


def test_slugify_non_ascii() -> None:
    slug = slugify("C'est l'été !")
    assert slug == "c-est-l-ete"

    # with a special space character
    slug = slugify("a_b\u205fc")  # U+205F: MEDIUM MATHEMATICAL SPACE
    assert slug == "a-b-c"

    # with non-ascii translatable chars, like EN DASH U+2013 and EM DASH
    # U+2014.
    # this test fails if regexp subst is done after Unicode normalization
    assert slugify("a\u2013b\u2014c") == "a-b-c"
