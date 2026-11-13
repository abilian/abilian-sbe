# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import abc

import sqlalchemy as sa
import sqlalchemy.event
from sqlalchemy import Column, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import backref, relationship

from abilian.core.entities import Entity, EntityQuery

from .blob import Blob

#: name of backref on target :class:`Entity` object
ATTRIBUTE = "__attachments__"


class SupportsAttachment(abc.ABC):  # noqa: B024
    """Mixin for entities that can have attachments."""


def register(cls):
    """Register an :class:`~.Entity` as an attachable class.

    Can be used as a class decorator:

    .. code-block:: python

      @attachment.register
      class MyContent(Entity):
          ....
    """
    if not issubclass(cls, Entity):
        msg = "Class must be a subclass of abilian.core.entities.Entity"
        raise TypeError(msg)

    SupportsAttachment.register(cls)
    return cls


def supports_attachments(obj):
    """
    :param obj: a class or instance

    :returns: True is obj supports attachments.
    """
    if isinstance(obj, type):
        return issubclass(obj, SupportsAttachment)

    if not isinstance(obj, SupportsAttachment):
        return False

    return obj.id is not None


def for_entity(obj, check_support_attachments=False):
    """Return attachments on an entity."""
    if check_support_attachments and not supports_attachments(obj):
        return []

    return getattr(obj, ATTRIBUTE)


class AttachmentQuery(EntityQuery):
    def all(self):
        return EntityQuery.all(self.order_by(Attachment.created_at))


class Attachment(Entity):
    """An Attachment owned by an :class:`Entity`."""

    __tablename__ = "attachment"
    __auditable_entity__ = ("entity", "attachment", ("id", "name"))

    entity_id = Column(Integer, ForeignKey(Entity.id), nullable=False)

    #: owning entity
    entity = relationship(
        Entity,
        lazy="immediate",
        foreign_keys=[entity_id],
        backref=backref(
            ATTRIBUTE,
            lazy="select",
            order_by="Attachment.created_at",
            cascade="all, delete-orphan",
        ),
    )

    blob_id = Column(Integer, sa.ForeignKey(Blob.id), nullable=False)
    #: file. Stored in a :class:`Blob`
    blob = relationship(Blob, cascade="all, delete", foreign_keys=[blob_id])

    description = Column(UnicodeText(), nullable=False, default="")

    query_class = AttachmentQuery

    def __repr__(self) -> str:
        class_ = self.__class__
        mod_ = class_.__module__
        classname = class_.__name__
        return f"<{mod_}.{classname} instance at 0x{id(self):x} entity id={self.entity_id!r}>"


@sa.event.listens_for(Attachment, "before_insert", propagate=True)
@sa.event.listens_for(Attachment, "before_update", propagate=True)
def set_attachment_name(mapper, connection, target) -> None:
    if target.name:
        return

    blob = target.blob
    if not blob:
        return

    filename = blob.meta.get("filename")
    if filename is not None:
        target.name = filename
