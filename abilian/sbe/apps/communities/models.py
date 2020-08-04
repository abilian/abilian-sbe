import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

import sqlalchemy as sa
from blinker import ANY
from flask import current_app
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, \
    Unicode, UniqueConstraint, and_
from sqlalchemy.event import listens_for
from sqlalchemy.orm import backref, relation, relationship
from sqlalchemy.orm.attributes import OP_APPEND, OP_REMOVE, Event
from sqlalchemy.sql.schema import Column
from werkzeug.local import LocalProxy

from abilian.core.entities import Entity, EntityMeta
from abilian.core.extensions import db
from abilian.core.models import NOT_AUDITABLE, SEARCHABLE
from abilian.core.models.blob import Blob
from abilian.core.models.subjects import Group, User
from abilian.i18n import _l
from abilian.sbe.apps.documents.models import Folder
from abilian.sbe.apps.documents.repository import repository
from abilian.services.indexing import indexable_role
from abilian.services.security import READ, WRITE, Admin
from abilian.services.security import Manager as MANAGER
from abilian.services.security import Permission
from abilian.services.security import Reader as READER
from abilian.services.security import Role, RoleType
from abilian.services.security import Writer as WRITER
from abilian.services.security import security

from . import signals

logger = logging.getLogger(__name__)

MEMBER = Role("member", label=_l("role_member"), assignable=False)
VALID_ROLES = frozenset([READER, WRITER, MANAGER, MEMBER])


class Membership(db.Model):
    """Represents the membership of someone in a community."""

    __tablename__ = "community_membership"

    id = Column(Integer, primary_key=True)

    user_id = Column(ForeignKey("user.id"), index=True, nullable=False)
    user = relationship(
        User, lazy="joined", backref=backref("communautes_membership", lazy="select")
    )

    community_id = Column(ForeignKey("community.id"), index=True, nullable=False)
    community = relationship("Community", lazy="joined")

    role = Column(RoleType())  # should be either 'member' or 'manager'

    __table_args__ = (UniqueConstraint("user_id", "community_id"),)

    def __repr__(self):
        return "<Membership user={}, community={}, role={}>".format(
            repr(self.user), repr(self.community), str(self.role)
        ).encode("utf-8")


def community_content(cls: type) -> Any:
    """Class decorator to mark models considered as community content.

    This is required for proper indexation.
    """
    cls.is_community_content = True

    def community_slug(self: Any) -> str:
        return self.community and self.community.slug

    cls.community_slug = property(community_slug)

    index_to = getattr(cls, "__index_to__", ())
    index_to += (("community_slug", ("community_slug",)),)
    cls.__index_to__ = index_to

    def _indexable_roles_and_users(self: Any) -> str:
        if not self.community:
            return []
        return indexable_roles_and_users(self.community)

    cls._indexable_roles_and_users = property(_indexable_roles_and_users)
    return cls


def indexable_roles_and_users(community: "Community") -> str:
    """Mixin to use to replace Entity._indexable_roles_and_users.

    Will be removed when communities are upgraded to use standard role
    based access (by setting permissions and using security service).
    """
    # TODO: remove
    return " ".join(indexable_role(user) for user in community.members)


class Community(Entity):
    """Ad-hoc objects that hold properties about a community."""

    __index_to__ = (("id", ("id", "community_id")),)

    is_community_content = True

    # : A public description.
    description = Column(Unicode(500), default="", nullable=False, info=SEARCHABLE)

    #: An image or logo for this community.
    image_id = Column(ForeignKey(Blob.id), index=True)
    image = relationship(Blob, lazy="joined")

    #: The root folder for this community.
    folder_id = Column(
        Integer,
        ForeignKey(Folder.id, use_alter=True, name="fk_community_root_folder"),
        unique=True,
    )
    folder = relation(
        Folder,
        single_parent=True,  # required for delete-orphan
        primaryjoin=(folder_id == Folder.id),
        cascade="all, delete-orphan",
        backref=backref("_community", lazy="select", uselist=False),
    )

    #: The group this community is linked to, if any. Memberships are then
    #: reflected
    group_id = Column(ForeignKey(Group.id), nullable=True, unique=True)
    group = relation(Group, foreign_keys=group_id, lazy="select")

    #: Memberships for this community.
    memberships = relationship(Membership, cascade="all, delete-orphan")

    #: direct access to :class:`User` members
    members = relationship(
        User,
        secondary=Membership.__table__,
        viewonly=True,
        backref=backref("communities", lazy="select", viewonly=True),
    )

    #: Number of members in this community.
    membership_count = Column(Integer, default=0, nullable=False, info=NOT_AUDITABLE)

    #: Number of documents in this community.
    document_count = Column(Integer, default=0, nullable=False, info=NOT_AUDITABLE)

    #: Last time something happened in this community
    last_active_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, info=NOT_AUDITABLE
    )

    # Various features for this community:

    #: True if this community has a document management space
    has_documents = Column(Boolean, nullable=False, default=True)

    #: True if this community has a wiki
    has_wiki = Column(Boolean, nullable=False, default=True)

    #: True if this community has a forum
    has_forum = Column(Boolean, nullable=False, default=True)

    #: One of 'participative' or 'informative
    type = Column(String(20), nullable=False, default="informative")

    #: One of 'secret', 'public', 'open' (currently not used)
    visibility = Column(String(20), nullable=False, default="secret")

    #: Used for segmenting communities. Not used currently.
    category = Column(String(20), nullable=False, default="")

    #: True if regular members can send stuff by email to all members
    # Not used anymore.
    members_can_send_by_email = Column(Boolean, nullable=False, default=False)

    def __init__(self, **kw):
        self.has_documents = True
        self.membership_count = 0
        self.document_count = 0
        self.members_can_send_by_email = False
        Entity.__init__(self, **kw)
        if self.has_documents and not self.folder:
            # FIXME: this should be done in documents by using signals
            name = self.name
            if not name:
                # during creation, we may have to provide a temporary name for
                # subfolder, we don't want empty names on folders since they must be
                # unique among siblings
                name = f"{self.__class__.__name__}_{str(self.id)}-{time.asctime()}"
            self.folder = repository.root_folder.create_subfolder(name)
            # if not self.group:
            #   self.group = Group(name=self.name)

        if not self.image:
            fn = Path(__file__).parent / "views" / "data" / "community.png"
            self.image = Blob(fn.open("rb").read())

    @property
    def has_calendar(self) -> bool:
        config = current_app.config
        return bool(config.get("ENABLE_CALENDAR"))

    def rename(self, name: str) -> None:
        self.name = name
        if self.folder:
            # FIXME: use signals
            self.folder.name = name

    def get_memberships(self, role: Optional[str] = None) -> List[Membership]:
        M = Membership
        memberships = M.query.filter(M.community_id == self.id)
        if role:
            memberships = memberships.filter(M.role == role)
        return memberships.all()

    def set_membership(self, user: User, role: Union[str, Role]) -> None:
        """Add a member with the given role, or set the role of an existing
        member."""
        assert isinstance(user, User)
        role = Role(role)

        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")

        session = sa.orm.object_session(self) or db.session()
        is_new = True
        M = Membership
        membership = (
            session.query(M)
            .filter(and_(M.user_id == user.id, M.community_id == self.id))
            .first()
        )

        if not membership:
            membership = Membership(community=self, user=user, role=role)
            session.add(membership)
            self.membership_count += 1
        else:
            is_new = False
            membership.role = role

        signals.membership_set.send(self, membership=membership, is_new=is_new)

    def remove_membership(self, user: User) -> None:
        M = Membership
        membership = M.query.filter(
            and_(M.user_id == user.id, M.community_id == self.id)
        ).first()
        if not membership:
            raise KeyError(f"User {user} is not a member of community {self}")

        db.session.delete(membership)
        self.membership_count -= 1
        signals.membership_removed.send(self, membership=membership)

    def update_roles_on_folder(self) -> None:
        if self.folder:
            self.ungrant_all_roles_on_folder()
            for membership in self.memberships:
                user = membership.user
                role = membership.role
                if role == MANAGER:
                    security.grant_role(user, MANAGER, self.folder)
                else:
                    if self.type == "participative":
                        security.grant_role(user, WRITER, self.folder)
                    else:
                        security.grant_role(user, READER, self.folder)

    def ungrant_all_roles_on_folder(self) -> None:
        if self.folder:
            role_assignments = security.get_role_assignements(self.folder)
            for principal, role in role_assignments:
                security.ungrant_role(principal, role, self.folder)

    def get_role(self, user: Union[User, LocalProxy]) -> Optional[Role]:
        """Returns the given user's role in this community."""
        M = Membership
        membership = (
            db.session()
            .query(M.role)
            .filter(and_(M.community_id == self.id, M.user_id == user.id))
            .first()
        )

        return membership.role if membership else None

    def has_member(self, user):
        return self.get_role(user) is not None

    def has_permission(self, user: LocalProxy, permission: Permission) -> bool:
        if not isinstance(permission, Permission):
            assert isinstance(permission, str)
            permission = Permission(permission)

        if user.has_role(Admin):
            return True
        role = self.get_role(user)
        if role == MANAGER:
            return True
        if role == MEMBER and permission in (READ, WRITE):
            return True
        return False

    def touch(self) -> None:
        self.last_active_at = datetime.utcnow()

    @property
    def _indexable_roles_and_users(self) -> str:
        return indexable_roles_and_users(self)


def CommunityIdColumn() -> Column:
    return Column(
        ForeignKey(Community.id),
        nullable=False,
        info=SEARCHABLE | {"index_to": (("community_id", ("community_id",)),)},
    )


# Handlers to keep community/group members in sync
#
_PROCESSED_ATTR = "__sbe_community_group_sync_processed__"


@signals.membership_set.connect_via(ANY)
def _membership_added(sender: Community, membership: Membership, is_new: bool) -> None:
    if not is_new:
        return

    if getattr(membership.user, _PROCESSED_ATTR, False) is OP_APPEND:
        return

    if sender.group and membership.user not in sender.group.members:
        logger.debug(
            "_membership_added(%r, %r, %r) user: %r",
            sender,
            membership,
            is_new,
            membership.user,
        )
        setattr(membership.user, _PROCESSED_ATTR, OP_APPEND)
        sender.group.members.add(membership.user)


@signals.membership_removed.connect_via(ANY)
def membership_removed(sender: Community, membership: Membership) -> None:
    if getattr(membership.user, _PROCESSED_ATTR, False) is OP_REMOVE:
        return

    if sender.group and membership.user in sender.group.members:
        logger.debug(
            "_membership_removed(%r, %r) user: %r", sender, membership, membership.user
        )
        setattr(membership.user, _PROCESSED_ATTR, OP_REMOVE)
        sender.group.members.discard(membership.user)


@listens_for(Community.members, "append")
@listens_for(Community.members, "remove")
def _on_member_change(community, user, initiator):
    group = community.group
    if not group:
        return

    logger.debug("_on_member_change(%r, %r, op=%r)", community, user, initiator.op)

    if getattr(user, _PROCESSED_ATTR, False) is initiator.op:
        return

    setattr(user, _PROCESSED_ATTR, initiator.op)

    if initiator.op is OP_APPEND:
        if user not in group.members:
            group.members.add(user)

    elif initiator.op is OP_REMOVE:
        if user in group.members:
            group.members.discard(user)


@listens_for(Community.group, "set", active_history=True)
def _on_linked_group_change(
    community: Community, value: Any, oldvalue: Any, initiator: Event
) -> None:
    if value == oldvalue:
        return

    logger.debug("_on_linked_group_change(%r, %r, %r)", community, value, oldvalue)

    if oldvalue is not None and oldvalue.members:
        logger.debug(
            "_on_linked_group_change(%r, %r, %r): oldvalue clear()",
            community,
            value,
            oldvalue,
        )
        oldvalue.members.clear()

    members = set(community.members)
    if value is not None and value.members != members:
        logger.debug(
            "_on_linked_group_change(%r, %r, %r): set value.members",
            community,
            value,
            oldvalue,
        )
        value.members = members


def _safe_get_community(group: Group) -> Optional[Community]:
    session = sa.orm.object_session(group)
    if not session:
        return None

    with session.no_autoflush:
        try:
            return (
                session.query(Community)
                .filter(Community.group == group)
                .options(
                    sa.orm.joinedload(Community.group),
                    sa.orm.joinedload(Community.members),
                )
                .one()
            )
        except sa.orm.exc.NoResultFound:
            return None


@listens_for(Group.members, "append")
@listens_for(Group.members, "remove")
def _on_group_member_change(group: Group, user: User, initiator: Event) -> None:
    community = _safe_get_community(group)

    if not community:
        return

    op = initiator.op
    if getattr(user, _PROCESSED_ATTR, False) is op:
        return

    is_present = user in community.members
    setattr(user, _PROCESSED_ATTR, op)
    logger.debug(
        "_on_group_member_change(%r, %r, op=%r) community: %r",
        group,
        user,
        initiator.op,
        community,
    )

    if (op is OP_APPEND and is_present) or (op is OP_REMOVE and not is_present):
        return

    if op is OP_APPEND:
        community.set_membership(user, MEMBER)

    elif op is OP_REMOVE:
        community.remove_membership(user)


@listens_for(Group.members, "set", active_history=True)
def _on_group_members_replace(group, value, oldvalue, initiator):
    if value == oldvalue:
        return

    community = _safe_get_community(group)
    if not community:
        return

    members = set(community.members)
    logger.debug(
        "_on_group_members_replace(%r, %r, %r) community: %r",
        group,
        value,
        oldvalue,
        community,
    )

    for u in members - value:
        if getattr(u, _PROCESSED_ATTR, False) is OP_REMOVE:
            continue
        setattr(u, _PROCESSED_ATTR, OP_REMOVE)
        community.remove_membership(u)

    for u in value - members:
        if getattr(u, _PROCESSED_ATTR, False) is OP_APPEND:
            continue
        setattr(u, _PROCESSED_ATTR, OP_APPEND)
        community.set_membership(u, MEMBER)
