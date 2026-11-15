# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Unicode, UnicodeText
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from abilian.core.entities import SEARCHABLE, Entity
from abilian.sbe.apps.communities.models import (
    Community,
    CommunityIdColumn,
    community_content,
)


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


@listens_for(Event.title, "set", active_history=True)
def _event_sync_name_title(entity, new_value, old_value, initiator):
    if entity.name != new_value:
        entity.name = new_value
    return new_value
