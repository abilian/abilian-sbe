# Copyright (c) 2012-2024, Abilian SAS

"""The rules: who may do what in a forum."""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.services import security_service
from abilian.services.security import OWNER, WRITE

if TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.sbe.apps.forum.models import Post


def can_write(user: User, post: Post) -> bool:
    """May `user` edit `post`? Its author, or a site admin.

    `OWNER` is a real role and `has_role` answers it against `object.owner`, so
    passing it as an additional valid role says "whoever may write this, plus
    whoever wrote it" without a clause of its own. Site admins come free: ADMIN
    is in every permission's role set.

    Deliberately not the community's managers. Closing and deleting a thread is
    moderation and theirs (`can_moderate`); rewriting somebody's message is a
    different act, and the UI has never offered it.
    """
    return security_service.has_permission(user, WRITE, post, roles=OWNER)
