# Copyright (c) 2012-2024, Abilian SAS

"""Social content items: messages aka status updates, private messages, etc."""

from __future__ import annotations

import re

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText

from abilian.core.entities import SEARCHABLE, Entity, EntityQuery
from abilian.core.models.subjects import Group, User

__all__ = ["Message", "PrivateMessage"]


class MessageQuery(EntityQuery):
    def by_creator(self, user):
        return self.filter(Message.creator_id == user.id)


class Message(Entity):
    """Message aka Status update aka Note.

    See: http://activitystrea.ms/head/activity-schema.html#note
    """

    __tablename__ = "message"
    __indexable__ = False
    __editable__ = ["content"]
    __exportable__ = [
        *__editable__,
        "id",
        "created_at",
        "updated_at",
        "creator_id",
        "owner_id",
    ]

    #: The content for this message.
    content: Mapped[str | None] = mapped_column(
        UnicodeText(), info=SEARCHABLE | {"index_to": ("text",)}
    )

    #: Nullable: if null, then message is public.
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(Group.id))

    #: The group this message has been posted to.
    group = relationship("Group", primaryjoin=(group_id == Group.id), lazy="joined")

    query_class = MessageQuery

    @property
    def tags(self) -> list[str]:
        return re.findall(r"(?u)#([^\W]+)", self.content)


# TODO: inheriting from Entity is overkill here
class TagApplication(Entity):
    __tablename__ = "tag_application"

    tag: Mapped[str | None] = mapped_column(Unicode(255), index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("message.id"))


class PrivateMessage(Entity):
    """Private messages are like messages, except they are private."""

    __tablename__ = "private_message"
    __indexable__ = False
    __editable__ = ["content", "recipient_id"]
    __exportable__ = [
        *__editable__,
        "id",
        "created_at",
        "updated_at",
        "creator_id",
        "owner_id",
    ]

    content: Mapped[str | None] = mapped_column(
        UnicodeText, info=SEARCHABLE | {"index_to": ("text",)}
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id), nullable=False
    )


class Like(Entity):
    __tablename__ = "like"
    __indexable__ = False
    __editable__ = ["content", "message_id"]
    __exportable__ = [
        *__editable__,
        "id",
        "created_at",
        "updated_at",
        "creator_id",
        "owner_id",
    ]

    content: Mapped[str | None] = mapped_column(
        UnicodeText, info=SEARCHABLE | {"index_to": ("text",)}
    )
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Message.id), nullable=False
    )
