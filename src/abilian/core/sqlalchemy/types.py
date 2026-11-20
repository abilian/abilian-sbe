# Copyright (c) 2012-2024, Abilian SAS

"""Additional data types for sqlalchemy."""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import TYPE_CHECKING, Any

import babel
import babel.dates
import pytz
import sqlalchemy as sa
import sqlalchemy.dialects
from sqlalchemy.ext.mutable import Mutable

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect
    from sqlalchemy.sql.sqltypes import CHAR


class MutationDict(Mutable, dict):
    """Provides a dictionary type with mutability support."""

    @classmethod
    def coerce(cls, key: str, value: dict) -> MutationDict:
        """Convert plain dictionaries to MutationDict."""
        if not isinstance(value, MutationDict):
            if isinstance(value, dict):
                return MutationDict(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        return value

    #  pickling support. see:
    #  http://docs.sqlalchemy.org/en/rel_0_8/orm/extensions/mutable.html#supporting-pickling
    def __getstate__(self) -> dict:
        return dict(self)

    def __setstate__(self, state: dict):
        self.update(state)

    # dict methods
    def __setitem__(self, key: str, value: int | str) -> None:
        """Detect dictionary set events and emit change events."""
        dict.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, key) -> None:
        """Detect dictionary del events and emit change events."""
        dict.__delitem__(self, key)
        self.changed()

    def clear(self) -> None:
        dict.clear(self)
        self.changed()

    def update(self, other, **kw) -> None:
        dict.update(self, other, **kw)
        self.changed()

    def setdefault(self, key, failobj=None):
        if key not in self:
            self.changed()
        return dict.setdefault(self, key, failobj)

    def pop(self, key, *args):
        self.changed()
        return dict.pop(self, key, *args)

    def popitem(self):
        self.changed()
        return dict.popitem(self)


class MutationList(Mutable, list):
    """Provides a list type with mutability support."""

    @classmethod
    def coerce(cls, key: str, value: list) -> MutationList:
        """Convert list to MutationList."""
        if not isinstance(value, MutationList):
            if isinstance(value, list):
                return MutationList(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        return value

    #  pickling support. see:
    #  http://docs.sqlalchemy.org/en/rel_0_8/orm/extensions/mutable.html#supporting-pickling
    def __getstate__(self):
        d = self.__dict__.copy()
        d.pop("_parents", None)
        return d

    # list methods
    def __setitem__(self, idx, value) -> None:
        list.__setitem__(self, idx, value)
        self.changed()

    def __delitem__(self, idx: Any) -> None:
        list.__delitem__(self, idx)
        self.changed()

    def insert(self, idx, value) -> None:
        list.insert(self, idx, value)
        self.changed()

    # def __setslice__(self, i, j, other):
    #     list.__setslice__(self, i, j, other)
    #     self.changed()
    #
    # def __delslice__(self, i, j):
    #     list.__delslice__(self, i, j)
    #     self.changed()

    def __iadd__(self, other):
        result = list.__iadd__(self, other)
        self.changed()
        return result

    def __imul__(self, n):
        result = list.__imul__(self, n)
        self.changed()
        return result

    def append(self, item: Any) -> None:
        list.append(self, item)
        self.changed()

    def pop(self, i=-1):
        item = list.pop(self, i)
        self.changed()
        return item

    def remove(self, item) -> None:
        list.remove(self, item)
        self.changed()

    def reverse(self) -> None:
        list.reverse(self)
        self.changed()

    def sort(self, *args, **kwargs) -> None:
        list.sort(self, *args, **kwargs)
        self.changed()

    def extend(self, other) -> None:
        list.extend(self, other)
        self.changed()


class JSON(sa.types.TypeDecorator):
    """Stores any structure serializable with json.

    Usage JSON() Takes same parameters as sqlalchemy.types.Text
    """

    impl = sa.types.Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(
        self, value: str | None, dialect: Dialect
    ) -> dict[str, Any] | list[int] | None:
        if value is not None:
            value = json.loads(value)
        return value


class JSONUniqueListType(JSON):
    """Store a list in JSON format, with items made unique and sorted."""

    cache_ok = True

    @property
    def python_type(self):
        return MutationList

    def process_bind_param(self, value, dialect):
        # value may be a simple string used in a LIKE clause for instance, so we
        # must ensure we uniquify/sort only for list-like values
        if value is not None and isinstance(value, (tuple, list)):
            value = sorted(set(value))

        return super().process_bind_param(value, dialect)


def JSONDict(*args, **kwargs):
    """Stores a dict as JSON on database, with mutability support."""
    return MutationDict.as_mutable(JSON(*args, **kwargs))


def JSONList(*args, **kwargs):
    """Stores a list as JSON on database, with mutability support.

    If kwargs has a param `unique_sorted` (which evaluated to True),
    list values are made unique and sorted.
    """
    type_ = JSON
    with contextlib.suppress(KeyError):
        if kwargs.pop("unique_sorted"):
            type_ = JSONUniqueListType

    return MutationList.as_mutable(type_(*args, **kwargs))


# TODO: replace byt UUIDType from sqlalchemy_util
class UUID(sa.types.TypeDecorator):
    """Platform-independent UUID type.

    Uses Postgresql's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    From SQLAlchemy documentation.
    """

    impl = sa.types.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> CHAR:
        if dialect.name == "postgresql":
            # Strings in and out, as this type converts them itself: SQLAlchemy
            # 2.0's PostgreSQL UUID would hand back uuid.UUID objects.
            return dialect.type_descriptor(sa.dialects.postgresql.UUID(as_uuid=False))
        return dialect.type_descriptor(sa.types.CHAR(32))

    def process_bind_param(
        self, value: str | uuid.UUID | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        # hexstring
        return value.hex

    def process_result_value(
        self, value: str | None, dialect: Dialect
    ) -> uuid.UUID | None:
        return value if value is None else uuid.UUID(value)

    def compare_against_backend(self, dialect, conn_type):
        if dialect.name == "postgresql":
            return isinstance(conn_type, sa.dialects.postgresql.UUID)
        return isinstance(conn_type, sa.types.CHAR)


class Locale(sa.types.TypeDecorator):
    """Store a :class:`babel.Locale` instance."""

    impl = sa.types.UnicodeText
    cache_ok = True

    @property
    def python_type(self):
        return babel.Locale

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> Any | None:
        if value is None:
            return None

        if not isinstance(value, babel.Locale):
            if not isinstance(value, str):
                msg = f"Unknown locale value: {format(repr(value))}"
                raise TypeError(msg)
            if not value.strip():
                return None
            value = babel.Locale.parse(value)

        code = str(value.language)
        if value.territory or value.script:
            code += f"_{value.territory!s}"

        return code

    def process_result_value(self, value: Any | None, dialect: Dialect) -> Any | None:
        return None if value is None else babel.Locale.parse(value)


class Timezone(sa.types.TypeDecorator):
    """Store a :class:`pytz.tzfile.DstTzInfo` instance."""

    impl = sa.types.UnicodeText
    cache_ok = True

    @property
    def python_type(self):
        return pytz.tzinfo.DstTzInfo

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> Any | None:
        if value is None:
            return None

        if not isinstance(value, pytz.tzinfo.DstTzInfo):
            if not isinstance(value, str):
                msg = f"Unknown timezone value: {value!r}"
                raise TypeError(msg)
            if not value.strip():
                return None
            value = babel.dates.get_timezone(value)

        return value.zone

    def process_result_value(self, value: Any | None, dialect: Dialect) -> Any | None:
        return None if value is None else babel.dates.get_timezone(value)
