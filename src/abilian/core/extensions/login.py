# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Concatenate, cast

from flask_login import AnonymousUserMixin, LoginManager, current_user as _current_user
from werkzeug.exceptions import Unauthorized

if TYPE_CHECKING:
    from collections.abc import Callable

    from abilian.core.models.subjects import Group, User


class AnonymousUser(AnonymousUserMixin):
    def has_role(self, role):
        from abilian.services import get_security_service

        security = get_security_service()
        return security.has_role(self, role)

    @property
    def groups(self) -> set[Group]:
        return set()


login_manager = LoginManager()
login_manager.anonymous_user = AnonymousUser

#: The user of the current request: flask-login's proxy, typed as what it
#: stands for. Anonymous visitors get an `AnonymousUser`, never None.
#:
#: Read it only where anonymous visitors are expected (authentication, the
#: menus). Everywhere else, the user is a parameter: a view gets it from
#: `authenticated`, and hands it down.
current_user = cast("User | AnonymousUser", _current_user)


def authenticated[**P, R](view: Callable[Concatenate[User, P], R]) -> Callable[P, R]:
    """Give a view the logged-in user, as its first argument.

    The view's signature then says that it needs one, and type checkers hold
    whatever it calls to a `User`.
    """

    @functools.wraps(view)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return view(authenticated_user(), *args, **kwargs)

    return wrapper


def authenticated_user() -> User:
    """The logged-in user, or a 401 for an anonymous visitor.

    Where a decorator cannot pass the user, as in class-based views and
    `before_request` hooks, call this once and pass its answer down.
    """
    user = current_user
    if isinstance(user, AnonymousUser):
        raise Unauthorized
    return user
