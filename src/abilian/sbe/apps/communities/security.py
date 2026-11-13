# Copyright (c) 2012-2024, Abilian SAS

"""The rules: who may do what in a community.

The route guards that enforce them are in `decorators.py`, one line
each. Nothing here reads a decorator and nothing there holds a rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import g
from flask_login import current_user
from werkzeug.exceptions import Forbidden

from abilian.core.util import BasePresenter
from abilian.sbe.apps.communities.models import VALID_ROLES
from abilian.services import security_service
from abilian.services.security import MANAGE

if TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.sbe.apps.communities.presenters import CommunityPresenter


def _unwrap(community: Any) -> Any:
    """`g.community` is a presenter, and the engine takes entities.

    `BasePresenter.__getattr__` forwards everything, which is why the old
    role-reading body never noticed -- but `has_role` asserts its object is an
    `Entity`, and a presenter is not one however well it forwards.
    """
    return community._model if isinstance(community, BasePresenter) else community


def check_membership(
    community: CommunityPresenter | None = None, user: User | None = None
) -> None:
    if not is_member(community, user):
        raise Forbidden


def is_member(
    community: CommunityPresenter | None = None, user: User | None = None
) -> bool:
    """Does `user` hold any role in `community`?

    Any of them: MANAGER, MEMBER, READER and WRITER all mean membership, which
    is why this asks `has_role` with the set rather than naming one. `has_role`
    seeds its valid roles with ADMIN and MANAGER, so a site admin passes
    without being a member -- as it did when that was a separate clause here.
    """
    if user is None:
        user = current_user
    if not community:
        community = getattr(g, "community", None)
    return security_service.has_role(user, VALID_ROLES, _unwrap(community))


def can_manage(community: Any, user: User | None = None) -> bool:
    """May `user` manage `community`?

    Asked of the policy engine, which is the point: `can_` promises a
    permission, and this used to be two role tests reading the member list --
    `is_site_admin(user) or community.get_role(user) == MANAGER`. Memberships
    are recorded as roles on the community itself now (`communities/events.py`),
    and MANAGE belongs to `{ADMIN, MANAGER}` in the engine's default matrix, so
    the engine can answer it.

    A site admin still passes without being a member, and still passes with no
    community at all: ADMIN is in every permission's role set, and
    `has_permission` checks global roles before object-local ones. That last
    case matters -- the route guard falls through to here when `g.community` is
    unset, and an admin must not start getting 403s there.
    """
    if user is None:
        user = current_user
    return security_service.has_permission(user, MANAGE, _unwrap(community))
