# coding=utf-8
"""
"""
from __future__ import absolute_import

from datetime import datetime
import time
from os.path import dirname, join

from flask import current_app
from sqlalchemy import Column, Unicode, ForeignKey, Boolean, DateTime, \
  Integer, UniqueConstraint, String, and_
from sqlalchemy.orm import relation, relationship, backref
import whoosh.fields as wf
from abilian.i18n import _l
from abilian.core.extensions import db
from abilian.core.models import NOT_AUDITABLE, SEARCHABLE
from abilian.core.models.subjects import Group, User
from abilian.core.entities import Entity
from abilian.services.indexing import indexable_role
from abilian.services.security import (
  Role, security, RoleType, Admin,
  Reader as READER,
  Writer as WRITER,
  Manager as MANAGER,
)

from abilian.sbe.apps.documents.repository import repository
from abilian.sbe.apps.documents.models import Folder, Blob
from . import signals

MEMBER = Role('member', label=_l(u'role_member'), assignable=False)
VALID_ROLES = frozenset((READER, WRITER, MANAGER, MEMBER,))


class Membership(db.Model):
  """
  Objects that represent the membership of someone in a community.
  """
  __tablename__ = 'community_membership'

  id = Column(Integer, primary_key=True)

  user_id = Column(ForeignKey('user.id'), index=True, nullable=False)
  user = relationship(User, lazy='joined',
                      backref=backref('communautes_membership', lazy='select'))

  community_id = Column(ForeignKey('community.id'), index=True, nullable=False)
  community = relationship('Community', lazy='joined')

  role = Column(RoleType())  # should be either 'member' or 'manager'

  __table_args__ = (UniqueConstraint('user_id', 'community_id'),)

  def __repr__(self):
    return u'<Membership user={}, community={}, role={}>'.format(
      repr(self.user),
      repr(self.community),
      str(self.role)
    ).encode('utf-8')


def community_content(cls):
  """
  Class decorator to mark models considered as community content. This is
  required for proper indexation.
  """
  cls.is_community_content = True

  def community_slug(self):
    return self.community and self.community.slug

  cls.community_slug = property(community_slug)
  index_to = cls.__indexation_args__.setdefault('index_to', ())
  index_to += (
    ('community_slug',
     (('community_slug', _whoosh_community_slug_field),),),
  )
  cls.__indexation_args__['index_to'] = index_to

  def _indexable_roles_and_users(self):
    if not self.community:
      return []
    return indexable_roles_and_users(self.community)

  cls._indexable_roles_and_users = property(_indexable_roles_and_users)
  return cls


def indexable_roles_and_users(community):
  """
  Mixin to use to replace Entity._indexable_roles_and_users.

  Will be removed when communities are upgraded to use standard role based
  access (by setting permissions and using security service).
  """
  return u' '.join(indexable_role(user)
                   for user in community.members)


class Community(Entity):
  """
  Ad-hoc objects that hold properties about a community.
  """
  __indexation_args__ = {}
  __indexation_args__.update(Entity.__indexation_args__)
  index_to = __indexation_args__.setdefault('index_to', ())
  index_to += (('id', ('id', 'community_id')),)
  __indexation_args__['index_to'] = index_to
  del index_to

  is_community_content = True

  # : A public description.
  description = Column(Unicode(500), default=u"", nullable=False,
                       info=SEARCHABLE)

  #: An image or logo for this community.
  image_id = Column(ForeignKey(Blob.id), index=True)
  image = relationship(Blob, lazy='joined')

  #: The root folder for this community.
  folder_id = Column(Integer,
                     ForeignKey(Folder.id, use_alter=True,
                                name='fk_community_root_folder'),
                     unique=True)
  folder = relation(Folder,
                    single_parent=True,  # required for delete-orphan
                    primaryjoin=(folder_id == Folder.id),
                    cascade='all, delete-orphan',
                    backref=backref('_community', lazy='select', uselist=False))

  #: The group this community is related to (members).
  group_id = Column(ForeignKey(Group.id))
  group = relation(Group, primaryjoin=(group_id == Group.id))

  #: Memberships for this community.
  memberships = relationship(Membership, cascade="all, delete-orphan")

  #: direct access to :class:`User` members
  members = relationship(User,
                         secondary=Membership.__table__,
                         backref=backref('communities', lazy='select'),)

  #: Number of members in this community.
  membership_count = Column(Integer, default=0, nullable=False,
                            info=NOT_AUDITABLE)

  #: Number of documents in this community.
  document_count = Column(Integer, default=0, nullable=False, info=NOT_AUDITABLE)

  #: Last time something happened in this community
  last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False,
                          info=NOT_AUDITABLE)

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
      #FIXME: this should be done in documents by using signals
      name = self.name
      if not name:
        # during creation, we may have to provide a temporary name for
        # subfolder, we don't want empty names on folders since they must be
        # unique among siblings
        name = u'{}_{}-{}'.format(self.__class__.__name__, str(self.id),
                                  time.asctime())
      self.folder = repository.root_folder.create_subfolder(name)
      #if not self.group:
    #  self.group = Group(name=self.name)

    if not self.image:
      fn = join(dirname(__file__), "data", "community.png")
      self.image = Blob(open(fn).read())

  def rename(self, name):
    self.name = name
    if self.folder:
      #FIXME: use signals
      self.folder.name = name

  def get_memberships(self, role=None):
    M = Membership
    memberships = M.query.filter(M.community_id == self.id)
    if role:
      memberships = memberships.filter(M.role == role)
    return memberships.all()

  def set_membership(self, user, role):
    """
    Add a member with the given role, or set the role of an existing
    member.
    """
    assert isinstance(user, User)
    role = Role(role)

    if role not in VALID_ROLES:
      raise ValueError("Invalid role: {}".format(role))

    is_new = True
    M = Membership
    membership = M.query \
      .filter(and_(M.user_id == user.id, M.community_id == self.id)).first()

    if not membership:
      membership = Membership(community=self, user=user, role=role)
      db.session.add(membership)
      self.membership_count += 1
    else:
      is_new = False
      membership.role = role

    if self.folder:
      #FIXME: this should be done in documents using signal membership_set
      local_role = WRITER if self.type == 'participative' else READER
      if role == MANAGER:
        local_role = MANAGER

      current_roles = set(security.get_roles(user, self.folder,
                                             no_group_roles=True))
      current_roles &= VALID_ROLES  # ensure we don't remove roles not managed
                                    # by us
      for role_to_ungrant in current_roles - set((local_role,)):
        security.ungrant_role(user, role_to_ungrant, self.folder)

      if local_role not in current_roles:
        security.grant_role(user, local_role, self.folder)

    signals.membership_set.send(self, membership=membership, is_new=is_new)

  def remove_membership(self, user):
    M = Membership
    membership = M.query \
      .filter(and_(M.user_id == user.id, M.community_id == self.id)).first()
    if not membership:
      raise KeyError(
        "User {} is not a member of community {}".format(user, self))

    signals.membership_removed.send(self, membership=membership)
    db.session.delete(membership)
    self.membership_count -= 1

    if self.folder:
      #FIXME: this should be done in documents using signal membership_removed
      roles = set(security.get_roles(user, self.folder, no_group_roles=True))
      roles &= VALID_ROLES  # ensure we don't remove roles not managed by us
      for role in roles:
        security.ungrant_role(user, role, self.folder)

  def update_roles_on_folder(self):
    if self.folder:
      self.ungrant_all_roles_on_folder()
      for membership in self.memberships:
        user = membership.user
        role = membership.role
        if role == MANAGER:
          security.grant_role(user, MANAGER, self.folder)
        else:
          if self.type == 'participative':
            security.grant_role(user, WRITER, self.folder)
          else:
            security.grant_role(user, READER, self.folder)

  def ungrant_all_roles_on_folder(self):
    if self.folder:
      role_assignments = security.get_role_assignements(self.folder)
      for principal, role in role_assignments:
        security.ungrant_role(principal, role, self.folder)

  def get_role(self, user):
    """
    Returns the current user's role in this community.
    """
    M = Membership
    membership = current_app.db.session()\
        .query(M.role)\
        .filter(and_(M.community_id == self.id,
                     M.user_id == user.id))\
        .first()

    return membership.role if membership else None

  def has_member(self, user):
    return self.get_role(user) is not None

  def has_permission(self, user, permission):
    if user.has_role(Admin):
      return True
    role = self.get_role(user)
    if role == MANAGER:
      return True
    if role == MEMBER and permission in ('read', 'write'):
      return True
    return False

  def touch(self):
    self.last_active_at = datetime.utcnow()

  @property
  def _indexable_roles_and_users(self):
    return indexable_roles_and_users(self)


_whoosh_community_id_field = wf.NUMERIC(numtype=int, bits=64, signed=False,
                                        stored=True, unique=False)
_whoosh_community_slug_field = wf.ID(stored=True)


def CommunityIdColumn():
  return Column(
    ForeignKey(Community.id),
    nullable=False,
    info=SEARCHABLE | dict(
      index_to=(
        ('community_id', _whoosh_community_id_field,),
      )),
  )
