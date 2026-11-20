# Copyright (c) 2026, Abilian SAS

"""The rules a new password follows, wherever it is chosen."""

from __future__ import annotations

from abilian.i18n import _

#: The fewest characters a password may have.
MIN_LENGTH = 8


def weakness(password: str) -> str | None:
    """What keeps `password` from being set, in words; None when it may be."""
    if len(password) < MIN_LENGTH:
        return _("Your new password must be at least 8 characters long")
    if password.lower() == password or password.upper() == password:
        return _("Your new password must contain upper case and lower case letters")
    if not any(c.isdigit() for c in password):
        return _("Your new password must contain at least one digit")
    return None
