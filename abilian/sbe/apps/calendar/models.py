# coding=utf-8
"""
"""
from __future__ import absolute_import, unicode_literals

from sqlalchemy import Column, DateTime, Unicode
from sqlalchemy.orm import backref, relationship

from abilian.core.entities import SEARCHABLE, Entity
from abilian.sbe.apps.communities.models import (Community, CommunityIdColumn,
                                                 community_content)


@community_content
class Event(Entity):
    __tablename__ = 'sbe_event'

    community_id = CommunityIdColumn()
    #: The community this event belongs to
    community = relationship(
        Community,
        primaryjoin=(community_id == Community.id),
        backref=backref('events', cascade="all, delete-orphan"))

    description = Column(Unicode, nullable=False, default="", info=SEARCHABLE)

    location = Column(Unicode, nullable=False, default="", info=SEARCHABLE)

    start = Column(DateTime, nullable=False)
    end = Column(DateTime)
