# Copyright (c) 2012-2024, Abilian SAS

"""Create a SQLAlchemy instance and configure it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
import sqlalchemy.event
import sqlalchemy.orm

from abilian.core.sqlalchemy import SQLAlchemy
from abilian.core.sqlalchemy.extension import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.sql.schema import MetaData

__all__ = ("db",)

# The session behaves as in SQLAlchemy 2.0. Notably, an object no longer joins
# the session through a backref: adding a child to a parent's collection, or
# giving it a parent, does not save it; add it to the session.


db = SQLAlchemy(model_class=Base, session_options={"future": True})


@sa.event.listens_for(db.metadata, "before_create")
@sa.event.listens_for(db.metadata, "before_drop")
def _filter_metadata_for_connection(
    target: MetaData, connection: Connection, **kw: Any
) -> None:
    """Listener to control what indexes get created.

    Useful for skipping postgres-specific indexes on a sqlite for example.

    It's looking for info entry `engines` on an index
    (`Index(info=dict(engines=['postgresql']))`), an iterable of engine names.
    """
    engine = connection.engine.name
    default_engines = (engine,)
    tables = target if isinstance(target, sa.Table) else kw.get("tables", [])
    for table in tables:
        indexes = list(table.indexes)
        for idx in indexes:
            if engine not in idx.info.get("engines", default_engines):
                table.indexes.remove(idx)


def _install_get_display_value(cls: Any) -> None:
    _MARK = object()

    def display_value(self, field_name, value=_MARK):
        """Return display value for fields having 'choices' mapping (stored
        value.

        -> human-readable value). For other fields it will simply return field
        value.

        `display_value` should be used instead of directly getting field value.

        If `value` is provided, it is "translated" to a human-readable value. This is
        useful for obtaining a human-readable label from a raw value.
        """
        val = getattr(self, field_name, "ERROR") if value is _MARK else value

        mapper = sa.orm.object_mapper(self)
        try:
            field = getattr(mapper.c, field_name)
        except AttributeError:
            pass
        else:
            if "choices" in field.info:

                def get(v):
                    return field.info["choices"].get(v, v)

                if isinstance(val, list):
                    val = [get(v) for v in val]
                else:
                    val = get(val)

        return val

    if not hasattr(cls, "display_value"):
        cls.display_value = display_value


sa.event.listen(db.Model, "class_instrument", _install_get_display_value)
