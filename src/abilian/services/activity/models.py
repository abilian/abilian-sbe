# Copyright (c) 2012-2024, Abilian SAS

"""Activity Service.

See: http://activitystrea.ms/specs/json/1.0/
See: http://activitystrea.ms/specs/atom/1.0/#activity
See: http://stackoverflow.com/questions/1443960/

TODO: Look wether other attributes from the spec need to be implemented.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey
from sqlalchemy.types import DateTime, Integer, String, Text

from abilian.core.entities import Entity, db
from abilian.core.models.subjects import User

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["ActivityEntry"]


def _default_from(column: str) -> Callable:
    """Helper for default and onupdates parameters in a Column definitions.

    Returns a `context-sensitive default function
    <http://docs.sqlalchemy.org/en/rel_0_8/core/defaults.html#context-
    sensitive-default-functions>`_ to set value from another column.
    """

    def _default_value(context):
        return context.current_parameters[column]

    return _default_value


class ActivityEntry(db.Model):
    """Main table for all activities."""

    __tablename__ = "activity_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    happened_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    verb: Mapped[str | None] = mapped_column(Text)

    actor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(User.id))
    actor = relationship(User, foreign_keys=actor_id)

    object_type: Mapped[str | None] = mapped_column(String(1000))
    object_id: Mapped[int | None] = mapped_column(
        Integer, default=_default_from("_fk_object_id")
    )
    _fk_object_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(Entity.id, ondelete="SET NULL")
    )
    object = relationship(Entity, foreign_keys=_fk_object_id)

    target_type: Mapped[str | None] = mapped_column(String(1000))
    target_id: Mapped[int | None] = mapped_column(
        Integer, default=_default_from("_fk_target_id")
    )
    _fk_target_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(Entity.id, ondelete="SET NULL")
    )
    target = relationship(Entity, foreign_keys=_fk_target_id)

    def __repr__(self) -> str:
        tpl = "<{}.ActivityEntry id={} actor={} verb={} object={} target={}>"
        return tpl.format(
            self.__class__.__module__,
            self.id,
            repr(str(self.actor)),
            repr(self.verb),
            repr(str(self.object)),
            repr(str(self.target)),
        )
