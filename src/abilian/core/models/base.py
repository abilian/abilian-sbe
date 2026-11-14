# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy.schema import Column
from sqlalchemy.types import DateTime, Integer
from whoosh.fields import ID

from abilian.core.extensions import db
from abilian.core.util import fqcn


#: Base Model class.
class Model(db.Model):
    __abstract__ = True


class Info(dict):
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            self[k] = v

    def copy(self) -> Info:
        # dict.copy would return an instance of dict
        return self.__class__(**self)

    def __add__(self, other: dict) -> Info:
        d = self.copy()
        d.update(other)
        return d

    __or__ = __add__


EDITABLE = Info(editable=True)
NOT_EDITABLE = Info(editable=False)
AUDITABLE = Info(auditable=True)
AUDITABLE_HIDDEN = Info(auditable=True, audit_hide_content=True)
NOT_AUDITABLE = Info(auditable=False)
SEARCHABLE = Info(searchable=True)
NOT_SEARCHABLE = Info(searchable=False)
EXPORTABLE = Info(exportable=True)
NOT_EXPORTABLE = Info(exportable=False)

#: SYSTEM properties are properties defined by the system
#: and not supposed to be changed manually.
SYSTEM = Info(editable=False, auditable=False)


class IdMixin:
    id = Column(Integer, primary_key=True, info=SYSTEM | SEARCHABLE)


#: What `__index_to__` holds: (attribute, fields) pairs, each field a field
#: name or a (name, whoosh field) pair.
IndexTo = tuple[tuple[str, tuple[str | tuple[str, Any], ...]], ...]


class Indexable:
    """Mixin with sensible defaults for indexable objects."""

    __indexable__ = True
    __index_to__: ClassVar[IndexTo] = (
        ("object_key", (("object_key", ID(stored=True, unique=True)),)),
        ("object_type", (("object_type", ID(stored=True)),)),
    )
    id: int

    @classmethod
    def _object_type(cls) -> str:
        return fqcn(cls)

    @property
    def object_type(self) -> str:
        return self._object_type()

    @property
    def object_key(self) -> str:
        return f"{self.object_type}:{self.id}"


class TimestampedMixin:
    #: creation date
    created_at = Column(DateTime, default=datetime.utcnow, info=SYSTEM | SEARCHABLE)
    #: last modification date
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        info=SYSTEM | SEARCHABLE,
    )
    deleted_at = Column(DateTime, default=None, info=SYSTEM)
