# Copyright (c) 2012-2024, Abilian SAS

"""Subject classes (i.e. people, groups, etc.).

See ICOM-ics-v1.0 "Subject Branch".

TODO: I'm not a big fan of the "subject" name. Could be replaced by something
else, like "people" or "principal" ?
"""

from __future__ import annotations

import random
import string
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import bcrypt
import sqlalchemy as sa
from flask_login import UserMixin
from flask_sqlalchemy.query import Query
from sqlalchemy.event import listens_for
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, deferred, relationship
from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import (
    Boolean,
    DateTime,
    Integer,
    LargeBinary,
    Unicode,
    UnicodeText,
)

from abilian.core import sqlalchemy as sa_types
from abilian.core.util import fqcn

from .base import SEARCHABLE, SYSTEM, IdMixin, Indexable, TimestampedMixin, db

if TYPE_CHECKING:
    from sqlalchemy.orm.mapper import Mapper

__all__ = (
    "ROOT_USER_ID",
    "ClearPasswordStrategy",
    "Group",
    "Principal",
    "User",
    "create_root_user",
    "gen_random_password",
)

# Tables for many-to-many relationships
following = db.Table(
    "following",
    db.Model.metadata,
    Column("follower_id", Integer, ForeignKey("user.id")),
    Column("followee_id", Integer, ForeignKey("user.id")),
    UniqueConstraint("follower_id", "followee_id"),
)

membership = db.Table(
    "membership",
    db.Model.metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("group.id", onupdate="CASCADE", ondelete="CASCADE"),
    ),
    UniqueConstraint("user_id", "group_id"),
)

# Should not be needed (?)
administratorship = db.Table(
    "administratorship",
    db.Model.metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("group.id", onupdate="CASCADE", ondelete="CASCADE"),
    ),
    UniqueConstraint("user_id", "group_id"),
)

_RANDOM_PASSWORD_CHARS = string.ascii_letters + string.digits + string.punctuation


def gen_random_password(length=15):
    rg = random.SystemRandom()
    return "".join(rg.choice(_RANDOM_PASSWORD_CHARS) for i in range(length))


class PasswordStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""

    @abstractmethod
    def authenticate(self, user: User, password: str) -> bool:
        """Predicate to tell wether password match user's or not."""

    @abstractmethod
    def process(self, user: User, password: str) -> str:
        """Return a string to be stored as user password."""


class ClearPasswordStrategy(PasswordStrategy):
    """Don't encrypt at all.

    This strategy should not ever be used elsewhere than in tests. It's
    useful in tests since a hash like bcrypt is designed to be slow.
    """

    @property
    def name(self) -> str:
        return "clear"

    def authenticate(self, user, password):
        return user.password == password

    def process(self, user, password):
        if not isinstance(password, str):
            password = password.decode("utf-8")
        return password


class BcryptPasswordStrategy(PasswordStrategy):
    """Hash passwords using bcrypt."""

    @property
    def name(self) -> str:
        return "bcrypt"

    def authenticate(self, user: User, password: str) -> bool:
        assert isinstance(password, str)

        current_passwd = user.password
        # crypt work only on bytes, not str (Unicode)
        if isinstance(current_passwd, str):
            current_passwd = current_passwd.encode("utf-8")
        if isinstance(password, str):
            password = password.encode("utf-8")

        return bcrypt.hashpw(password, current_passwd) == current_passwd

    def process(self, user: User, password: str) -> str:
        if isinstance(password, str):
            password = password.encode("utf-8")
        return bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8")


class UserQuery(Query):
    def get_by_email(self, email):
        return self.filter_by(email=email).one()


class Principal(IdMixin, TimestampedMixin, Indexable):
    """A principal is either a User or a Group."""

    __index_to__ = (("name", ("name", "name_prefix", "text")),)

    query_class = UserQuery
    query: UserQuery

    def has_role(self, role, context=None):
        from abilian.services import get_security_service

        security_service = get_security_service()
        return security_service.has_role(self, role, context)


def set_entity_type(cls: type[User | Group]) -> type[User | Group]:
    """Decorator used to set the class' entity_type after the class has been
    declared.

    Actually, it works using __module__ during class declaration, but
    linters (Flake8, PyCharm) complain.
    """
    cls.entity_type = fqcn(cls)
    return cls


@set_entity_type
class User(Principal, UserMixin, db.Model):
    __tablename__ = "user"
    __editable__ = ["first_name", "last_name", "email", "password"]
    __exportable__ = [*__editable__, "created_at", "updated_at", "id"]

    __password_strategy__ = BcryptPasswordStrategy()

    # Basic information
    first_name = Column(UnicodeText, info=SEARCHABLE)
    last_name = Column(UnicodeText, info=SEARCHABLE)
    # Should we add gender, salutation ?

    # System information
    email = Column(Unicode(255), nullable=False)  # for Mariadb set length of varchar
    can_login = Column(Boolean, nullable=False, default=True)
    password = Column(UnicodeText, default="*", info={"audit_hide_content": True})

    photo = deferred(Column(LargeBinary))

    last_active = Column(DateTime, info=SYSTEM)
    locale = Column(sa_types.Locale, nullable=True, default=None)
    timezone = Column(sa_types.Timezone, nullable=True, default=None)

    __table_args__ = (UniqueConstraint("email"),)

    followers = relationship(
        "User",
        secondary=following,
        primaryjoin="User.id == following.c.follower_id",
        secondaryjoin="User.id == following.c.followee_id",
        backref="followees",
    )

    def __init__(self, password=None, **kwargs) -> None:
        Principal.__init__(self)
        UserMixin.__init__(self)
        db.Model.__init__(self, **kwargs)

        if self.can_login and password is not None:
            self.set_password(password)
            self._password = password

    def authenticate(self, password: str) -> bool:
        if self.password and self.password != "*":  # noqa: S105
            return self.__password_strategy__.authenticate(self, password)
        return False

    def set_password(self, password: str) -> None:
        """Encrypts and sets password."""
        self.password = self.__password_strategy__.process(self, password)

    def follow(self, followee) -> None:
        if followee == self:
            msg = "User can't follow self"
            raise Exception(msg)
        self.followees.append(followee)

    def unfollow(self, followee) -> None:
        if followee == self:
            msg = "User can't follow self"
            raise Exception(msg)
        i = self.followees.index(followee)
        del self.followees[i]

    def join(self, group) -> None:
        self.groups.add(group)

    def leave(self, group) -> None:
        if group in self.groups:
            self.groups.remove(group)

    #
    # Boolean properties
    #
    def is_following(self, other) -> bool:
        return other in self.followees

    def is_member_of(self, group) -> bool:
        return self in group.members

    def is_admin_of(self, group) -> bool:
        return self in group.admins

    @property
    def is_online(self):
        if self.last_active is None:
            return False
        return datetime.utcnow() - self.last_active <= timedelta(minutes=1)

    #
    # Other properties
    #
    @property
    def name(self) -> str:
        name = f"{(self.first_name or '')} {(self.last_name or '')}"
        return name.strip() or "Unknown"

    @property
    def short_name(self):
        first_name = self.first_name or ""
        last_name = f"{self.last_name[0:1]}." if self.last_name else ""
        name = f"{first_name} {last_name}"
        return name.strip() or "Unknown"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        cls = self.__class__
        return f"<{cls.__module__}.{cls.__name__} id={self.id!r} email={self.email!r} at 0x{id(self):x}>"


@listens_for(User, "mapper_configured", propagate=True)
def _add_user_indexes(mapper: Mapper, cls: type[User]) -> None:
    # this is a functional index (indexes on a function result), we cannot define
    # it in __table_args__.
    #
    # see: https://groups.google.com/d/msg/sqlalchemy/CgSJUlelhGs/_Nj3f201hs4J
    idx = sa.schema.Index(
        "user_unique_lowercase_email", sa.sql.func.lower(cls.email), unique=True
    )
    idx.info["engines"] = ("postgresql",)


@set_entity_type
class Group(Principal, db.Model):
    __indexable__ = False
    __tablename__ = "group"
    __editable__ = ["name", "description"]
    __exportable__ = [*__editable__, "created_at", "updated_at", "id"]

    name = Column(UnicodeText, nullable=False, info=SEARCHABLE)
    description = Column(UnicodeText, info=SEARCHABLE)
    photo = deferred(Column(LargeBinary))
    public = Column(Boolean, default=False, nullable=False)

    members = relationship(
        "User",
        collection_class=set,
        secondary=membership,
        backref=backref("groups", lazy="select", collection_class=set),
    )
    admins = relationship("User", collection_class=set, secondary=administratorship)

    @hybrid_property
    def members_count(self):
        return len(self.members)

    @members_count.expression
    def members_count(cls):
        return (
            sa.sql.select([sa.sql.func.count(membership.c.user_id)])
            .where(membership.c.group_id == cls.id)
            .group_by(membership.c.group_id)
            .label("members_count")
        )


#: The SYSTEM principal. Not a person: it is what actions taken with no acting
#: user are attributed to. Created by `flask initdb`, not by `create_all`, so
#: code that looks it up must cope with it being absent.
ROOT_USER_ID = 0


def create_root_user() -> User:
    user = User.query.get(ROOT_USER_ID)
    if user is None:
        user = User(
            id=ROOT_USER_ID,
            last_name="SYSTEM",
            email="system@example.com",
            can_login=False,
        )
        db.session.add(user)
        db.session.commit()
    return user
