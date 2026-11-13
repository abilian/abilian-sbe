# Copyright (c) 2012-2024, Abilian SAS

"""Route guards, each named for the check it enforces.

One line of enforcement each, over a predicate that holds the rule. The name is
the predicate's name on purpose -- `@can_manage` requires `can_manage` -- so
there is nowhere for the two to drift apart, and so a guard cannot quietly
describe itself as something it does not ask.

That last part is why the site-admin guard is `@is_site_admin` and not
`can_admin`: it tests a site-wide *role*, the same one for every object, and a
`can_`-prefixed name would have claimed a permission on the object at hand.
`can_admin`, if it is ever wanted, is that other question -- ADMIN on a given
object -- and nothing asks it today.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any

from flask import g
from werkzeug.exceptions import Forbidden

from abilian.sbe.apps.communities.security import (
    can_manage as _can_manage,
)
from abilian.services.security import is_site_admin as _is_site_admin

if TYPE_CHECKING:
    from collections.abc import Callable

    from werkzeug.wrappers import Response


def is_site_admin(func: Callable) -> Callable:
    @wraps(func)
    def decorated_view(*args: Any, **kwargs: Any) -> str | Response:
        if not _is_site_admin():
            raise Forbidden
        return func(*args, **kwargs)

    return decorated_view


def can_manage(func: Callable) -> Callable:
    @wraps(func)
    def decorated_view(*args: Any, **kwargs: Any) -> Response:
        if not _can_manage(g.community):
            raise Forbidden
        return func(*args, **kwargs)

    return decorated_view
