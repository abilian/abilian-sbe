"""Social content items: messages aka status updates, private messages, etc."""
import re
from typing import List

from sqlalchemy.orm import relationship
from sqlalchemy.orm.query import Query
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import Integer, UnicodeText

from abilian.core.entities import SEARCHABLE, Entity
from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User

__all__ = ["Message", "PrivateMessage"]


class MessageQuery(Query):
    def by_creator(self, user):
        return self.filter(Message.creator_id == user.id)


class Message(Entity):
    """Message aka Status update aka Note.

    See: http://activitystrea.ms/head/activity-schema.html#note
    """

    __tablename__ = "message"
    __indexable__ = False
    __editable__ = ["content"]
    __exportable__ = __editable__ + [
        "id",
        "created_at",
        "updated_at",
        "creator_id",
        "owner_id",
    ]

    #: The content for this message.
    content = Column(UnicodeText(), info=SEARCHABLE | {"index_to": ("text",)})

    #: Nullable: if null, then message is public.
    group_id = Column(Integer, ForeignKey(Group.id))

    #: The group this message has been posted to.
    group = relationship("Group", primaryjoin=(group_id == Group.id), lazy="joined")

    query = db.session.query_property(MessageQuery)

    @property
    def tags(self) -> List[str]:
        return re.findall(r"(?u)#([^\W]+)", self.content)


# TODO: inheriting from Entity is overkill here
class TagApplication(Entity):
    __tablename__ = "tag_application"

    tag = Column(UnicodeText, index=True)
    message_id = Column(Integer, ForeignKey("message.id"))


class PrivateMessage(Entity):
    """Private messages are like messages, except they are private."""

    __tablename__ = "private_message"
    __indexable__ = False
    __editable__ = ["content", "recipient_id"]
    __exportable__ = __editable__ + [
        "id",
        "created_at",
        "updated_at",
        "creator_id",
        "owner_id",
    ]

    content = Column(UnicodeText, info=SEARCHABLE | {"index_to": ("text",)})
    recipient_id = Column(Integer, ForeignKey(User.id), nullable=False)


class Like(Entity):

    __tablename__ = "like"
    __indexable__ = False
    __editable__ = ["content", "message_id"]
    __exportable__ = __editable__ + [
        "id",
        "created_at",
        "updated_at",
        "creator_id",
        "owner_id",
    ]

    content = Column(UnicodeText, info=SEARCHABLE | {"index_to": ("text",)})
    message_id = Column(Integer, ForeignKey(Message.id), nullable=False)
