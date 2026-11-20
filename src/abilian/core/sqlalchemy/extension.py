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

    class DeclaredModel(Base, FlaskModel):
        """What `db.Model` is, for type checkers: the declarative base, typed
        (constructor, `__table__`, `registry`), with Flask-SQLAlchemy's
        `query`."""

        __abstract__ = True


class SQLAlchemy(SAExtension):
    """Base subclass of :class:`flask_sqlalchemy.SQLAlchemy`, typing its models."""

    Model: type[DeclaredModel]
