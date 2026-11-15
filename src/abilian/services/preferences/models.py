# Copyright (c) 2012-2024, Abilian SAS

"""Models for user preferences."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from abilian.core.extensions import db
from abilian.core.models.subjects import User
from abilian.core.sqlalchemy import JSON


class UserPreference(db.Model):
    """An atom of user preference."""

    __tablename__ = "user_preference"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    #: Unique id for this preference.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: The user who set this preference.
    user = relationship(
        User, backref=backref("preferences", cascade="all, delete, delete-orphan")
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id))

    #: The key
    key: Mapped[str] = mapped_column(String(255), nullable=False)

    #: The value
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
