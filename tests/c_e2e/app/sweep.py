# Copyright (c) 2012-2024, Abilian SAS

"""Request every route of the application, for the access sweeps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import g, url_for

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from flask.testing import FlaskClient
    from werkzeug.test import TestResponse

    from abilian.app import Application

IGNORED_METHODS = frozenset({"HEAD", "OPTIONS"})


def request_every_route(
    app: Application,
    client: FlaskClient,
    values: Mapping[str, Any],
    skip: Callable[[str], bool],
) -> Iterator[tuple[str, TestResponse]]:
    """Request each route with each of its methods, but for the endpoints
    `skip` leaves out, and yield `"METHOD url"` with the response.

    URL arguments come from `values`, and are 1 when missing there.

    Each request starts with the `g` it would have in production. In a test,
    requests reuse the fixture's app context, so a request would otherwise see
    what the previous one left in `g` -- a `g.community`, for one, makes the
    next request check membership in that community.
    """
    before = set(vars(g))
    for rule in app.url_map.iter_rules():
        if skip(rule.endpoint):
            continue
        url = url_for(
            rule.endpoint, **{arg: values.get(arg, 1) for arg in rule.arguments}
        )
        for method in sorted(rule.methods - IGNORED_METHODS):
            response = client.open(url, method=method)
            for key in set(vars(g)) - before:
                delattr(g, key)
            yield f"{method} {url}", response
