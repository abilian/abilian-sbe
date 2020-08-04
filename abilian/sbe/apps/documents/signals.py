from typing import Any

from abilian.sbe.apps.communities.models import VALID_ROLES, Community, \
    Membership
from abilian.sbe.apps.communities.signals import membership_removed, \
    membership_set
from abilian.services.security import Manager, Reader, Writer, security

from .search import reindex_tree


@membership_set.connect
def new_community_member(
    community: Community, membership: Membership, is_new: bool, **kwargs: Any
) -> None:
    if not community.folder:
        return

    role = membership.role
    user = membership.user
    local_role = Writer if community.type == "participative" else Reader
    if role == Manager:
        local_role = Manager

    current_roles = set(security.get_roles(user, community.folder, no_group_roles=True))
    current_roles &= VALID_ROLES  # ensure we don't remove roles not managed
    # by us

    for role_to_ungrant in current_roles - {local_role}:
        security.ungrant_role(user, role_to_ungrant, community.folder)

    if local_role not in current_roles:
        security.grant_role(user, local_role, community.folder)

    reindex_tree(community.folder)


@membership_removed.connect
def remove_community_member(
    community: Community, membership: Membership, **kwargs: Any
) -> None:
    if not community.folder:
        return

    user = membership.user
    roles = set(security.get_roles(user, community.folder, no_group_roles=True))
    roles &= VALID_ROLES  # ensure we don't remove roles not managed by us
    for role in roles:
        security.ungrant_role(user, role, community.folder)

    reindex_tree(community.folder)
