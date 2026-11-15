# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey
from sqlalchemy.types import DateTime, Integer

from abilian.core.entities import Entity, db
from abilian.core.models.subjects import User


# TODO: remove duplicate
def _default_from(column):
    """Helper for default and onupdates parameters in a Column definitions.

    Returns a `context-sensitive default function
    <http://docs.sqlalchemy.org/en/rel_0_8/core/defaults.html#context-
    sensitive-default-functions>`_ to set value from another column.
    """

    def _default_value(context):
        return context.current_parameters[column]

    return _default_value


class View(db.Model):
    __tablename__ = "view"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, nullable=False
    )

    #: viewed entity id
    entity_id: Mapped[int] = mapped_column(
        Integer, default=_default_from("_fk_entity_id"), nullable=False
    )
    _fk_entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(Entity.id, ondelete="SET NULL")
    )
    entity = relationship(Entity, foreign_keys=_fk_entity_id)

    #: user id
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id), nullable=False)
    user = relationship(User, foreign_keys=user_id)

    hits = relationship("Hit", backref="view", order_by="Hit.viewed_at", lazy="dynamic")


class Hit(db.Model):
    __tablename__ = "hit"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, nullable=False
    )
    view_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(View.id))

    #: time of view
    viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
