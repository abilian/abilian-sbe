from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import dateutil.parser
from flask import current_app
from flask_login import current_user

from abilian.core.models.subjects import User
from abilian.core.util import utcnow

DEFAULT_LIFETIME = 3600


class Lock:
    """Represent a lock on a document."""

    def __init__(
        self,
        user_id: int,
        user: str,
        date: Union[datetime, str],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.user_id = user_id
        self.user = user
        if not isinstance(date, datetime):
            try:
                date = dateutil.parser.parse(date)
            except Exception as e:
                raise ValueError(f"Error parsing date: {date!r}") from e

        self.date = date

    @staticmethod
    def new() -> "Lock":
        return Lock(current_user.id, str(current_user), utcnow())

    def as_dict(self) -> Dict[str, Any]:
        """Return a dict suitable for serialization to JSON."""
        return {
            "user_id": self.user_id,
            "user": self.user,
            "date": self.date.isoformat(),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Lock":
        """Deserialize from a `dict` created by :meth:`as_dict`."""
        return Lock(**d)

    @property
    def lifetime(self) -> int:
        return current_app.config.get("SBE_LOCK_LIFETIME", DEFAULT_LIFETIME)

    @property
    def expired(self) -> bool:
        return (utcnow() - self.date) > timedelta(seconds=self.lifetime)

    def is_owner(self, user: Optional[User] = None) -> bool:
        if user is None:
            user = current_user

        return self.user_id == user.id
