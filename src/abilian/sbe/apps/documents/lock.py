# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import dateutil.parser
from flask import current_app

from abilian.core.util import utcnow

if TYPE_CHECKING:
    from abilian.core.models.subjects import User

DEFAULT_LIFETIME = 3600


class Lock:
    """Represent a lock on a document."""

    def __init__(
        self,
        user_id: int,
        user: str,
        date: datetime | str,
    ) -> None:
        self.user_id = user_id
        self.user = user
        if not isinstance(date, datetime):
            try:
                date = dateutil.parser.parse(date)
            except Exception as e:
                msg = f"Error parsing date: {date!r}"
                raise ValueError(msg) from e

        self.date = date

    @staticmethod
    def new(user: User) -> Lock:
        return Lock(user.id, str(user), utcnow())

    def as_dict(self) -> dict[str, Any]:
        """Return a dict suitable for serialization to JSON."""
        return {
            "user_id": self.user_id,
            "user": self.user,
            "date": self.date.isoformat(),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Lock:
        """Deserialize from a `dict` created by :meth:`as_dict`."""
        return Lock(**d)

    @property
    def lifetime(self) -> int:
        return current_app.config.get("SBE_LOCK_LIFETIME", DEFAULT_LIFETIME)

    @property
    def expired(self) -> bool:
        return (utcnow() - self.date) > timedelta(seconds=self.lifetime)

    def is_owner(self, user: User) -> bool:
        return self.user_id == user.id
