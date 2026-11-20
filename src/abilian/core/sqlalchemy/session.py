# Copyright (c) 2012-2024, Abilian SAS

"""The session an object belongs to."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def session_of(obj: object) -> Session:
    """Return the session `obj` belongs to.

    For code that needs one: unlike `object_session()`, this never returns
    None, and says so when `obj` belongs to no session.
    """
    session = sa.orm.object_session(obj)
    if session is None:
        msg = f"{obj!r} belongs to no session"
        raise sa.exc.InvalidRequestError(msg)
    return session
