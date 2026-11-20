# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from abilian.core.entities import SEARCHABLE, Entity
from abilian.sbe.apps.communities.models import (
    Community,
    CommunityIdColumn,
    community_content,
)
from abilian.sbe.apps.documents.models import BaseContent
from abilian.sbe.apps.forum.models import Thread


@community_content
class Event(Entity):
    __tablename__ = "sbe_event"

    community_id = CommunityIdColumn()
    #: The community this event belongs to
    community = relationship(
        Community,
        primaryjoin=(community_id == Community.id),
        backref=backref("events", cascade="all, delete-orphan"),
    )

    title: Mapped[str] = mapped_column(
        Unicode(255), nullable=False, default="", info=SEARCHABLE
    )

    description: Mapped[str] = mapped_column(
        UnicodeText, nullable=False, default="", info=SEARCHABLE
    )

    location: Mapped[str] = mapped_column(
        UnicodeText, nullable=False, default="", info=SEARCHABLE
    )

    start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end: Mapped[datetime | None] = mapped_column(DateTime)

    url: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="")

    #: Where the event is discussed, once someone started a discussion about it.
    thread_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(Thread.id, ondelete="SET NULL")
    )
    thread = relationship(Thread, foreign_keys=[thread_id])


class EventAttachment(BaseContent):
    """A file attached to an event, as a wiki page's are."""

    __tablename__: str = None
    __indexable__ = False
    __mapper_args__ = {"polymorphic_identity": "event_attachment"}
    sbe_type = "event:attachment"

    _event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(Event.id), nullable=True
    )
    event = relationship(
        Event,
        primaryjoin=(_event_id == Event.id),
        backref=backref(
            "attachments",
            lazy="select",
            order_by="EventAttachment.name",
            cascade="all, delete-orphan",
        ),
    )


@listens_for(Event.title, "set", active_history=True)
def _event_sync_name_title(entity, new_value, old_value, initiator):
    if entity.name != new_value:
        entity.name = new_value
    return new_value
