# coding=utf-8
"""
"""
from __future__ import absolute_import

from datetime import datetime

import sqlalchemy as sa
from flask import g
from sqlalchemy import (Column, DateTime, ForeignKey, Integer, Unicode,
                        UnicodeText, UniqueConstraint)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship

from abilian.core.entities import SEARCHABLE, Entity, db
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import (Community, CommunityIdColumn,
                                                 community_content)
from abilian.sbe.apps.documents.models import BaseContent

from . import markup

__all__ = ['WikiPage']


@community_content
class WikiPage(Entity):
    __tablename__ = 'wiki_page'

    # : The title for this page
    _title = Column('title', Unicode(200), nullable=False, index=True)

    community_id = CommunityIdColumn()
    #: The community this page belongs to
    community = relationship(
        Community,
        primaryjoin=(community_id == Community.id),
        backref=backref("wiki", cascade="all, delete-orphan"))

    #: The body, using some markup language (Markdown for now)
    body_src = Column(UnicodeText,
                      default=u"",
                      nullable=False,
                      info=SEARCHABLE | dict(index_to=('text',)))

    __table_args__ = (UniqueConstraint('title', 'community_id'),)

    def __init__(self, title=u"", body_src=u"", message=u"", *args, **kwargs):
        Entity.__init__(self, *args, **kwargs)
        self.title = title
        self.create_revision(body_src, message)

    # title is defined has an hybrid property to allow name <-> title sync (2 way)
    @hybrid_property
    def title(self):
        return self._title

    @title.setter
    def title(self, title):
        # set title before setting name, so that we don't enter an infinite loop
        # with _wiki_sync_name_title
        self._title = title
        if self.name != title:
            self.name = title

    def create_revision(self, body_src, message=u""):
        revision = WikiPageRevision()
        if self.revisions:
            revision.number = max(r.number for r in self.revisions) + 1
        else:
            revision.number = 0
        self.body_src = revision.body_src = body_src
        revision.message = message
        revision.author = g.user
        revision.page = self

    @property
    def last_revision(self):
        return WikiPageRevision.query\
            .filter(WikiPageRevision.page == self)\
            .order_by(WikiPageRevision.number.desc())\
            .first()

    @property
    def body_html(self):
        html = markup.convert(self, self.body_src)
        return html

        # TODO: remove Javascript from content
        #return bleach.clean(html, strip=True)


@sa.event.listens_for(WikiPage.name, "set", active_history=True)
def _wiki_sync_name_title(entity, new_value, old_value, initiator):
    """
    Synchronize wikipage name -> title.
    wikipage.title -> name is done via hybrid_property, avoiding infinite
    loop (since "set" is received before attribute has received value)
    """
    if entity.title != new_value:
        entity.title = new_value
    return new_value


class WikiPageRevision(db.Model):
    __tablename__ = 'wiki_page_revision'
    __table_args__ = (UniqueConstraint('page_id', 'number'),)

    # : Some primary key just in case
    id = Column(Integer, primary_key=True)

    #: Date and time this revision was created
    created_at = Column(DateTime, default=datetime.utcnow)

    #: The page this revision belongs to
    page = relationship(WikiPage, backref='revisions')
    page_id = Column(ForeignKey(WikiPage.id))

    #: The revision number
    number = Column(Integer, nullable=False)

    #: The body, using some markup language (Markdown for now)
    body_src = Column(UnicodeText, default=u"", nullable=False)

    #: Commit message
    message = Column(UnicodeText, default=u"", nullable=False)

    #: The author of this revision
    author = relationship(User)
    author_id = Column(ForeignKey(User.id))


class WikiPageAttachment(BaseContent):
    __tablename__ = None
    __indexable__ = False
    __mapper_args__ = {'polymorphic_identity': 'wikipage_attachment'}
    sbe_type = 'wikipage:attachment'

    _wikipage_id = Column(Integer, ForeignKey(WikiPage.id), nullable=True)
    wikipage = relationship(WikiPage,
                            primaryjoin=(_wikipage_id == WikiPage.id),
                            backref=backref('attachments',
                                            lazy='select',
                                            order_by='WikiPageAttachment.name',
                                            cascade='all, delete-orphan'))
