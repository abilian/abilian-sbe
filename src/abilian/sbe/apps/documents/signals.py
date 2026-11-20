# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from abilian.sbe.apps.communities.roles import clear_roles, set_exclusive_role
from abilian.sbe.apps.communities.signals import membership_removed, membership_set
from abilian.services.security import MANAGER, READER, WRITER

from .search import reindex_tree

if TYPE_CHECKING:
    from abilian.sbe.apps.communities.models import Community, Membership


@membership_set.connect
def new_community_member(
    community: Community, membership: Membership, is_new: bool, **kwargs: Any
) -> None:
    if not community.folder:
        return

    role = membership.role
    user = membership.user
    local_role = WRITER if community.type == "participative" else READER
    if role == MANAGER:
        local_role = MANAGER

    set_exclusive_role(user, local_role, community.folder)
    reindex_tree(community.folder)


@membership_removed.connect
def remove_community_member(
    community: Community, membership: Membership, **kwargs: Any
) -> None:
    if not community.folder:
        return

    clear_roles(membership.user, community.folder)
    reindex_tree(community.folder)
