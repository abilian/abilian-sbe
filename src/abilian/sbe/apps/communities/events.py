# Copyright (c) 2012-2024, Abilian SAS

"""Lightweight integration and denormalisation using events (signals)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from blinker import ANY

from abilian.core.signals import activity
from abilian.sbe.apps.documents.models import Document

from .models import Community
from .roles import clear_roles, set_exclusive_role
from .signals import membership_removed, membership_set

if TYPE_CHECKING:
    from abilian.core.entities import Entity
    from abilian.core.models.subjects import User


@activity.connect_via(ANY)
def update_community(
    sender: Any, verb: str, actor: User, object: Entity, target: Entity | None = None
) -> None:
    if isinstance(object, Community):
        object.touch()
        return

    if isinstance(target, Community):
        community = target
        community.touch()

        if isinstance(object, Document):
            match verb:
                case "post":
                    community.document_count += 1
                case "delete":
                    community.document_count -= 1


@membership_set.connect_via(ANY)
def grant_role_on_community(
    sender: Community, membership: Any, is_new: bool, **kwargs: Any
) -> None:
    """Record the membership as a role on the community itself.

    Without this the engine cannot answer `has_permission(user, MANAGE,
    community)` -- nothing granted a role there -- which is why `can_manage`
    had to be hand-written as two role tests. `MANAGE` belongs to `{ADMIN,
    MANAGER}` in the engine's default matrix, so no `PermissionAssignment` row
    is needed for the grant to mean something.
    """
    set_exclusive_role(membership.user, membership.role, sender)


@membership_removed.connect_via(ANY)
def ungrant_roles_on_community(
    sender: Community, membership: Any, **kwargs: Any
) -> None:
    clear_roles(membership.user, sender)
