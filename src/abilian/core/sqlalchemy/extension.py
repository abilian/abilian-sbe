# Copyright (c) 2012-2024, Abilian SAS

"""Additional data types for sqlalchemy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_sqlalchemy import SQLAlchemy as SAExtension
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The models' base: Flask-SQLAlchemy builds `db.Model` on it.

    Flask-SQLAlchemy types `db.Model` as its own class whatever the base, so
    `SQLAlchemy.Model` below says what it is.
    """


if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model as FlaskModel
    from sqlalchemy.orm import Session, scoped_session

    class ScopedSession(scoped_session, Session):
        """What a `scoped_session` offers, for type checkers.

        SQLAlchemy 1.4 builds its proxy methods at runtime, where no type
        checker sees them: besides its own methods, it offers what a Session
        does, and calling it returns the current Session.
        """

        def __call__(self) -> Session:
            """Return the current Session."""

    class DeclaredModel(Base, FlaskModel):
        """What `db.Model` is, for type checkers: the declarative base, typed
        (constructor, `__table__`, `registry`), with Flask-SQLAlchemy's
        `query`."""

        __abstract__ = True


class SQLAlchemy(SAExtension):
    """Base subclass of :class:`flask_sqlalchemy.SQLAlchemy`, typing it."""

    session: ScopedSession
    Model: type[DeclaredModel]
