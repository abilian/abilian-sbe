from datetime import datetime
from typing import Union

from flask_login import current_user
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Unicode, \
    UnicodeText, UniqueConstraint
from sqlalchemy.event import listens_for
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.attributes import Event
from sqlalchemy.util.langhelpers import _symbol

from abilian.core.entities import Entity, db
from abilian.core.models import SEARCHABLE
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import Community, CommunityIdColumn, \
    community_content
from abilian.sbe.apps.documents.models import BaseContent

__all__ = ["WikiPage", "WikiPageAttachment", "WikiPageRevision"]


@community_content
class WikiPage(Entity):
    __tablename__ = "wiki_page"

    # : The title for this page
    _title = Column("title", Unicode(200), nullable=False, index=True)

    community_id = CommunityIdColumn()
    #: The community this page belongs to
    community = relationship(
        Community,
        primaryjoin=(community_id == Community.id),
        backref=backref("wiki", cascade="all, delete-orphan"),
    )

    #: The body, using some markup language (Markdown for now)
    body_src = Column(
        UnicodeText,
        default="",
        nullable=False,
        info=SEARCHABLE | {"index_to": ("text",)},
    )

    __table_args__ = (UniqueConstraint("title", "community_id"),)

    def __init__(self, title="", body_src="", message="", *args, **kwargs):
        Entity.__init__(self, *args, **kwargs)
        self.title = title
        self.create_revision(body_src, message)

    # title is defined has an hybrid property to allow name <-> title sync
    # (2 way)
    @hybrid_property
    def title(self: str) -> str:
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        # set title before setting name, so that we don't enter an infinite loop
        # with _wiki_sync_name_title
        self._title = title
        if self.name != title:
            self.name = title

    def create_revision(self, body_src: str, message: str = "") -> None:
        revision = WikiPageRevision()
        if self.revisions:
            revision.number = max(r.number for r in self.revisions) + 1
        else:
            revision.number = 0
        self.body_src = revision.body_src = body_src
        revision.message = message
        revision.author = current_user
        revision.page = self

    @property
    def last_revision(self) -> "WikiPageRevision":
        return (
            WikiPageRevision.query.filter(WikiPageRevision.page == self)
            .order_by(WikiPageRevision.number.desc())
            .first()
        )

    @property
    def body_html(self) -> str:
        from . import markup

        html = markup.convert(self, self.body_src)
        return html

        # TODO: remove Javascript from content
        # return bleach.clean(html, strip=True)


@listens_for(WikiPage.name, "set", active_history=True)
def _wiki_sync_name_title(
    entity: WikiPage, new_value: str, old_value: Union[_symbol, str], initiator: Event
) -> str:
    """Synchronize wikipage name -> title.

    wikipage.title -> name is done via hybrid_property, avoiding
    infinite loop (since "set" is received before attribute has received
    value)
    """
    if entity.title != new_value:
        entity.title = new_value
    return new_value


class WikiPageRevision(db.Model):
    __tablename__ = "wiki_page_revision"
    __table_args__ = (UniqueConstraint("page_id", "number"),)

    # : Some primary key just in case
    id = Column(Integer, primary_key=True)

    #: Date and time this revision was created
    created_at = Column(DateTime, default=datetime.utcnow)

    #: The page this revision belongs to
    page = relationship(WikiPage, backref="revisions")
    page_id = Column(ForeignKey(WikiPage.id))

    #: The revision number
    number = Column(Integer, nullable=False)

    #: The body, using some markup language (Markdown for now)
    body_src = Column(UnicodeText, default="", nullable=False)

    #: Commit message
    message = Column(UnicodeText, default="", nullable=False)

    #: The author of this revision
    author = relationship(User)
    author_id = Column(ForeignKey(User.id))


class WikiPageAttachment(BaseContent):
    __tablename__: str = None
    __indexable__ = False
    __mapper_args__ = {"polymorphic_identity": "wikipage_attachment"}
    sbe_type = "wikipage:attachment"

    _wikipage_id = Column(Integer, ForeignKey(WikiPage.id), nullable=True)
    wikipage = relationship(
        WikiPage,
        primaryjoin=(_wikipage_id == WikiPage.id),
        backref=backref(
            "attachments",
            lazy="select",
            order_by="WikiPageAttachment.name",
            cascade="all, delete-orphan",
        ),
    )
