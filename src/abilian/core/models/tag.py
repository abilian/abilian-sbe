# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import abc
from functools import total_ordering
from typing import Any

import sqlalchemy as sa
import sqlalchemy.orm

from abilian.core.entities import Entity
from abilian.core.extensions import db

from .base import IdMixin, Model

#: backref attribute on tagged elements
TAGS_ATTR = "__tags__"


class SupportTagging(abc.ABC):
    id: Any | None


def register(cls):
    """Register an :class:`~.Entity` as a taggable class.

    Can be used as a class decorator:

    .. code-block:: python

        @tag.register
        class MyContent(Entity):
            ....
    """
    if not issubclass(cls, Entity):
        msg = "Class must be a subclass of abilian.core.entities.Entity"
        raise TypeError(msg)

    SupportTagging.register(cls)
    return cls


def supports_tagging(obj) -> bool:
    """
    :param obj: a class or instance
    """
    if isinstance(obj, type):
        return issubclass(obj, SupportTagging)

    if not isinstance(obj, SupportTagging):
        return False

    return obj.id is not None


entity_tag_tbl = db.Table(
    "entity_tags",
    Model.metadata,
    sa.Column("tag_id", sa.Integer, sa.ForeignKey("tag.id", ondelete="CASCADE")),
    sa.Column("entity_id", sa.Integer, sa.ForeignKey(Entity.id, ondelete="CASCADE")),
    sa.UniqueConstraint("tag_id", "entity_id"),
)


@total_ordering
class Tag(IdMixin, Model):
    """Tags are text labels that can be attached to :class:`entities.Entity`.

    They are namespaced, so that independent group of tags can be
    defined in the application. The default namespace is `"default"`.
    """

    __tablename__ = "tag"

    #: namespace

    # for Mariadb set length of varchar:
    ns = sa.Column(
        sa.Unicode(255), nullable=False, default="default", server_default="default"
    )

    #: Label visible to the user
    label = sa.Column(sa.Unicode(255), nullable=False)

    #: :class:`entities <.Entity>` attached to this tag
    entities = sa.orm.relationship(
        Entity,
        collection_class=set,
        secondary=entity_tag_tbl,
        backref=sa.orm.backref(TAGS_ATTR, collection_class=set),
    )

    # __mapper_args__ = {"order_by": label}

    __table_args__ = (
        sa.UniqueConstraint(ns, label),
        # namespace is not empty and is not surrounded by space characters
        sa.CheckConstraint(sa.sql.and_(sa.sql.func.trim(ns) == ns, ns != "")),
        # label is not empty and is not surrounded by space characters
        sa.CheckConstraint(sa.sql.and_(sa.sql.func.trim(label) == label, label != "")),
    )

    def __str__(self) -> str:
        return self.label

    def __lt__(self, other):
        return str(self).lower().__lt__(str(other).lower())

    def __repr__(self) -> str:
        cls = self.__class__
        return (
            f"<{cls.__module__}.{cls.__name__} id={self.id!r} ns={self.ns!r} "
            f"label={self.label!r} at 0x{id(self):x}>"
        )
