# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from urllib.parse import parse_qs

import pytest
from flask import Flask

from abilian.web.listing import PER_PAGE, Listing

SORT_KEYS = {"name": str.lower, "length": len}
NAMES = ["bob", "Alice", "carol"]


def _rows(url: str, rows=tuple(NAMES), prefix: str = "") -> tuple[Listing, list[str]]:
    with Flask(__name__).test_request_context(url):
        return Listing.from_rows(rows, SORT_KEYS, "name", str, prefix=prefix)


def _in_request(url: str, call):
    with Flask(__name__).test_request_context(url):
        return call(Listing.from_request(SORT_KEYS, "name"))


def test_rows_use_the_default_sort() -> None:
    assert _rows("/")[1] == ["Alice", "bob", "carol"]


def test_a_minus_sign_reverses_the_sort() -> None:
    listing, rows = _rows("/?sort=-name")
    assert rows == ["carol", "bob", "Alice"]
    assert listing.descending


def test_rows_sort_by_the_column_asked_for() -> None:
    assert _rows("/?sort=length")[1] == ["bob", "Alice", "carol"]


@pytest.mark.parametrize("sort", ["nope", "-nope", "__class__"])
def test_an_unknown_sort_falls_back_to_the_default(sort: str) -> None:
    listing, rows = _rows(f"/?sort={sort}")
    assert listing.sort == "name"
    assert not listing.descending
    assert rows == ["Alice", "bob", "carol"]


def test_the_filter_ignores_case_and_surrounding_space() -> None:
    listing, rows = _rows("/?q=%20LIC%20")
    assert rows == ["Alice"]
    assert listing.search == "LIC"
    assert listing.total == 1


def test_the_filter_is_plain_text_not_a_pattern() -> None:
    assert _rows("/?q=(")[1] == []
    assert _rows("/?q=.*")[1] == []


def test_rows_are_cut_into_pages() -> None:
    rows = [f"{i:03}" for i in range(PER_PAGE + 3)]

    listing, first = _rows("/", rows)
    assert first == rows[:PER_PAGE]
    assert (listing.pages, listing.page) == (2, 1)
    assert (listing.start, listing.stop) == (0, PER_PAGE)

    listing, second = _rows("/?page=2", rows)
    assert second == rows[PER_PAGE:]
    assert (listing.start, listing.stop) == (PER_PAGE, PER_PAGE + 3)


@pytest.mark.parametrize(
    ("page", "expected"), [("99", 2), ("0", 1), ("-3", 1), ("abc", 1)]
)
def test_a_page_out_of_range_shows_the_nearest_one(page: str, expected: int) -> None:
    rows = [f"{i:03}" for i in range(PER_PAGE + 3)]
    assert _rows(f"/?page={page}", rows)[0].page == expected


def test_no_rows_is_one_empty_page() -> None:
    listing, rows = _rows("/", ())
    assert rows == []
    assert (listing.pages, listing.page, listing.start, listing.stop) == (1, 1, 0, 0)


@pytest.mark.parametrize(
    ("page", "expected"),
    [(1, [1, 2, 3, 4, 5]), (6, [4, 5, 6, 7, 8]), (20, [16, 17, 18, 19, 20])],
)
def test_page_links_are_a_window_around_the_current_page(
    page: int, expected: list[int]
) -> None:
    rows = list(map(str, range(20 * PER_PAGE)))
    assert list(_rows(f"/?page={page}", rows)[0].page_links) == expected


def test_page_links_stop_at_the_last_page() -> None:
    rows = list(map(str, range(2 * PER_PAGE)))
    assert list(_rows("/", rows)[0].page_links) == [1, 2]


def test_clicking_a_column_sorts_ascending_then_descending() -> None:
    assert _in_request("/", lambda t: t.sort_url("length")) == "?sort=length"
    assert _in_request("/?sort=length", lambda t: t.sort_url("length")) == (
        "?sort=-length"
    )
    assert _in_request("/?sort=-length", lambda t: t.sort_url("length")) == (
        "?sort=length"
    )
    # "name" is already the default, and it is ascending.
    assert _in_request("/", lambda t: t.sort_url("name")) == "?sort=-name"


def test_links_keep_the_rest_of_the_query_string() -> None:
    url = _in_request("/?q=a+b&page=3&sort=length", lambda t: t.page_url(4))
    assert parse_qs(url[1:]) == {"q": ["a b"], "page": ["4"], "sort": ["length"]}


def test_sorting_goes_back_to_the_first_page() -> None:
    url = _in_request("/?q=a&page=3", lambda t: t.sort_url("name"))
    assert parse_qs(url[1:]) == {"q": ["a"], "sort": ["-name"]}


def test_the_filter_form_keeps_the_sort_but_not_the_page() -> None:
    fields = _in_request(
        "/?q=a&page=3&sort=-name&tab=x", lambda t: sorted(t.filter_fields())
    )
    assert fields == [("sort", "-name"), ("tab", "x")]


def test_two_tables_on_a_page_do_not_share_their_state() -> None:
    url = "/?a_q=ali&a_page=2&a_sort=-name&q=bob"

    listing, rows = _rows(url, prefix="a_")
    assert (listing.search, listing.descending) == ("ali", True)
    assert rows == ["Alice"]

    other, rows = _rows(url, prefix="b_")
    assert (other.search, other.sort, other.requested_page) == ("", "name", 1)
    assert len(rows) == 3

    with Flask(__name__).test_request_context(url):
        table = Listing.from_request(SORT_KEYS, "name", prefix="b_")
        assert parse_qs(table.page_url(2)[1:]) == {
            "a_q": ["ali"],
            "a_page": ["2"],
            "a_sort": ["-name"],
            "q": ["bob"],
            "b_page": ["2"],
        }
        assert ("a_q", "ali") in table.filter_fields()
        assert table.param("q") == "b_q"
