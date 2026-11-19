# Copyright (c) 2012-2024, Abilian SAS

"""Filter, sort and page a server-rendered table from the query string.

The state lives in the URL (`?q=ann&sort=-email&page=2`), so every table works
with plain links, and a filtered page can be bookmarked or shared. A prefix keeps
two tables on one page out of each other's way. `macros/listing.html` renders the
controls.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from flask import request
from sqlalchemy import inspect
from sqlalchemy.sql.expression import asc, desc, func, or_

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping

PER_PAGE = 50
PAGE_LINKS = 5


def by_name(user: Any) -> tuple[str, str]:
    """Sort key for people: last name, then first name, ignoring case."""
    return (user.last_name or "").lower(), (user.first_name or "").lower()


@dataclass(frozen=True)
class Listing:
    search: str
    sort: str
    descending: bool
    requested_page: int
    prefix: str = ""
    total: int = 0

    @classmethod
    def from_request(
        cls, sortable: Collection[str], default_sort: str, prefix: str = ""
    ) -> Listing:
        """Read the query string. Anything it cannot use falls back to the default."""
        sort = request.args.get(f"{prefix}sort", "")
        key = sort.removeprefix("-")
        known = key in sortable
        return cls(
            search=request.args.get(f"{prefix}q", "").strip(),
            sort=key if known else default_sort,
            descending=known and sort.startswith("-"),
            requested_page=request.args.get(f"{prefix}page", 1, type=int),
            prefix=prefix,
        )

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[Any],
        sort_keys: Mapping[str, Callable[[Any], Any]],
        default_sort: str,
        text: Callable[[Any], str],
        prefix: str = "",
    ) -> tuple[Listing, list[Any]]:
        """Filter, sort and page rows that are already in memory.

        `text` gives what the filter searches in a row.
        """
        listing = cls.from_request(sort_keys, default_sort, prefix)
        matching = [row for row in rows if listing.matches(text(row))]
        matching.sort(key=sort_keys[listing.sort], reverse=listing.descending)
        listing = replace(listing, total=len(matching))
        return listing, matching[listing.start : listing.stop]

    @classmethod
    def from_query(
        cls,
        query: Any,
        sort_columns: Mapping[str, tuple[Any, ...]],
        default_sort: str,
        search_columns: tuple[Any, ...],
    ) -> tuple[Listing, list[Any]]:
        """Filter, sort and page in the database."""
        listing = cls.from_request(sort_columns, default_sort)
        query = listing.filter(query, search_columns)
        listing = replace(listing, total=query.count())
        direction = desc if listing.descending else asc
        # Empty values go last. MariaDB has no NULLS LAST, so sort on IS NULL
        # first. Each page is its own query, so rows that tie must still have
        # one order, or a row can land on two pages or on none.
        primary_key = inspect(query.column_descriptions[0]["entity"]).primary_key
        ordering = [
            term
            for column in sort_columns[listing.sort]
            for term in (column.is_(None), direction(column))
        ]
        ordering += [direction(column) for column in primary_key]
        rows = query.order_by(*ordering).slice(listing.start, listing.stop).all()
        return listing, rows

    def matches(self, text: str) -> bool:
        """Whether a row in memory, by what the filter searches in it, is kept."""
        return self.search.lower() in text.lower()

    def filter(self, query: Any, search_columns: tuple[Any, ...]) -> Any:
        """The rows of a query the filter keeps: so a tab can count them too."""
        if not self.search:
            return query
        wanted = self.search.lower()
        return query.filter(
            or_(
                *(
                    func.lower(column).contains(wanted, autoescape=True)
                    for column in search_columns
                )
            )
        )

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // PER_PAGE))

    @property
    def page(self) -> int:
        """The page asked for, or the nearest one that exists."""
        return min(max(self.requested_page, 1), self.pages)

    @property
    def start(self) -> int:
        return (self.page - 1) * PER_PAGE

    @property
    def stop(self) -> int:
        return min(self.start + PER_PAGE, self.total)

    @property
    def page_links(self) -> range:
        first = max(1, min(self.page - PAGE_LINKS // 2, self.pages - PAGE_LINKS + 1))
        return range(first, min(first + PAGE_LINKS - 1, self.pages) + 1)

    def param(self, name: str) -> str:
        return f"{self.prefix}{name}"

    def page_url(self, page: int) -> str:
        return self._url(page=page)

    def sort_url(self, key: str) -> str:
        """Sort by this column: ascending first, then the other way round."""
        ascending_now = self.sort == key and not self.descending
        return self._url(sort=f"-{key}" if ascending_now else key, page=None)

    def filter_fields(self) -> list[tuple[str, str]]:
        """What the filter form must resend: all but the filter and the page."""
        replaced = {self.param("q"), self.param("page")}
        return [
            (name, value)
            for name, value in request.args.items(multi=True)
            if name not in replaced
        ]

    def _url(self, **changes: int | str | None) -> str:
        args = request.args.to_dict(flat=False)
        for name, value in changes.items():
            if value is None:
                args.pop(self.param(name), None)
            else:
                args[self.param(name)] = [str(value)]
        return f"?{urlencode(args, doseq=True)}"
