# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask import Blueprint

from abilian.core.application import as_application
from abilian.services.security import ANONYMOUS, Role

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from abilian.core.models.subjects import User
    from abilian.services.security.service import SecurityService


def allow_anonymous(user: User, roles: Collection[Role], **kwargs: Any) -> bool:
    return True


def allow_access_for_roles(roles: Collection[Role] | Role) -> Callable:
    """Access control helper to check user's roles against a list of valid
    roles."""
    if isinstance(roles, Role):
        roles = (roles,)
    valid_roles = frozenset(roles)

    if ANONYMOUS in valid_roles:
        return allow_anonymous

    # FIXME: parameter not used. Why?
    def check_role(user: User, roles: Collection[Role], **kwargs):
        from abilian.services import get_service

        security: SecurityService = cast("SecurityService", get_service("security"))
        return security.has_role(user, valid_roles)

    return check_role


class AccessControlBlueprint(Blueprint):
    """An enhanced :class:`flask.blueprints.Blueprint` with access control
    helpers."""

    def __init__(
        self,
        name: str,
        import_name: str,
        allowed_roles: str | Role | Collection[Role] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        :param allowed_roles: role or list of roles required to access any view in this
            blueprint.
        """
        super().__init__(name, import_name, **kwargs)

        if allowed_roles is not None:
            if isinstance(allowed_roles, str):
                allowed_roles = Role(allowed_roles)

            if isinstance(allowed_roles, Role):
                allowed_roles = (allowed_roles,)
        else:
            allowed_roles = ()

        if allowed_roles:
            self.record_once(
                lambda s: as_application(s.app).add_access_controller(
                    self.name, allow_access_for_roles(allowed_roles)
                )
            )

    def allow_any(self, func) -> None:
        pass
