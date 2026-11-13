# Copyright (c) 2012-2024, Abilian SAS

"""Additional data types for sqlalchemy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_sqlalchemy import SQLAlchemy as SAExtension

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, scoped_session

    class ScopedSession(scoped_session, Session):
        """What a `scoped_session` offers, for type checkers.

        SQLAlchemy 1.4 builds its proxy methods at runtime, where no type
        checker sees them: besides its own methods, it offers what a Session
        does, and calling it returns the current Session.
        """

        def __call__(self) -> Session:
            """Return the current Session."""


class SQLAlchemy(SAExtension):
    """Base subclass of :class:`flask_sqlalchemy.SQLAlchemy`, typing its session."""

    session: ScopedSession
