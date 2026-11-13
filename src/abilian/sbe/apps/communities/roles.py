# Copyright (c) 2012-2024, Abilian SAS

"""Projecting a membership onto an object as a role.

A community membership is a single role: a user is a manager of a community or
a member of it, never both. Two places record that projection -- the community
itself (`events.py`) and its folder, which content inherits from
(`documents/signals.py`) -- and "make this the only one" is the same rule in
both, so it is written once here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.sbe.apps.communities.models import VALID_ROLES
from abilian.services.security import security

if TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.services.security import Role


def set_exclusive_role(user: User, role: Role, obj: object) -> None:
    """Make `role` the only community role `user` holds on `obj`.

    Roles outside `VALID_ROLES` are left alone: a folder may carry grants that
    nothing here manages, and removing them is not this function's business.
    """
    current = set(security.get_roles(user, obj, no_group_roles=True)) & VALID_ROLES

    for stale in current - {role}:
        security.ungrant_role(user, stale, obj)

    if role not in current:
        security.grant_role(user, role, obj)


def clear_roles(user: User, obj: object) -> None:
    """Remove every community role `user` holds on `obj`."""
    for role in set(security.get_roles(user, obj, no_group_roles=True)) & VALID_ROLES:
        security.ungrant_role(user, role, obj)
