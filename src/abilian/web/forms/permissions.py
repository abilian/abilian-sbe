# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask_login import current_user
from wtforms import Field

from abilian.core.entities import Entity
from abilian.services import get_service
from abilian.services.security import (
    ANONYMOUS,
    CREATE,
    READ,
    WRITE,
    Permission,
    Role,
    SecurityService,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from abilian.core.models.subjects import User


class FormPermissions:
    """Form role/permission manager."""

    def __init__(
        self,
        default: Role = ANONYMOUS,
        *,
        read: Role | Collection[Role] | None = None,
        write: Role | Collection[Role] | None = None,
        fields_read: dict[str, Collection[Role]] | None = None,
        fields_write: dict[str, Collection[Role]] | None = None,
        existing: Any | None = None,
    ) -> None:
        """
        :param default: default roles when not specified for field. Can be:

            * a :class:`Role` or an iterable of :class:`Role`

            * a callable that returns a :class:`Role` or an iterable of
              :class:`Role`

            * a `dict` with :class:`Permission` instances for keys and one of other
              acceptable role spec.; a default entry `"default"` is required.

        :param read: global roles required for `READ` permission for whole form.

        :param write: global roles required for `WRITE` permission for whole form.
        """
        if isinstance(default, Role):
            default_dict = {"default": (default,)}
        elif isinstance(default, dict):
            if "default" not in default:
                msg = '`default` parameter must have a "default" key'
                raise ValueError(msg)
            default_dict = default
        elif callable(default):
            default_dict = {"default": default}
        else:
            msg = (
                "No valid value for `default`. Use a Role, an iterable "
                "of Roles, a callable, or a dict."
            )
            raise TypeError(msg)

        self.default = default_dict
        self.form: dict[Permission, Any] = {}
        self.fields: dict[str, dict[Permission, Collection[Role]]] = {}

        if existing is not None:
            # copy existing formpermissions instance
            # maybe overwrite later with our definitions
            assert isinstance(existing, FormPermissions)
            for permission in (READ, WRITE):
                if permission in existing.form:
                    self.form[permission] = existing.form[permission]

            for field, mapping in existing.fields.items():
                f_map = self.fields[field] = {}
                for permission, roles in mapping.items():
                    f_map[permission] = roles

        for permission, roles in ((READ, read), (WRITE, write)):
            match roles:
                case None:
                    continue
                case Role():
                    roles = (roles,)
            self.form[permission] = roles

        fields_defs = (
            (fields_read, READ),
            (fields_write, WRITE),
            (fields_write, CREATE),
        )  # checking against CREATE permission
        # at field level is the same as
        # WRITE permisssion
        for fields, permission in fields_defs:
            if fields:
                for field_name, allowed_roles in fields.items():
                    if isinstance(allowed_roles, Role):
                        allowed_roles = (allowed_roles,)
                    self.fields.setdefault(field_name, {})[permission] = allowed_roles

    def has_permission(
        self,
        permission: Permission,
        field: str | None = None,
        obj: Entity | object | None = None,
        user: User | None = None,
    ) -> bool:
        if user is None:
            user = cast("User", current_user)
        if obj is not None and not isinstance(obj, Entity):
            # permission/role can be set only on entities
            return True

        # FIXME: permission is not a str
        allowed_roles = (
            self.default[permission]
            if permission in self.default
            else self.default["default"]
        )
        definition = None

        def eval_roles(fun: Callable) -> list[Role]:
            return fun(permission=permission, field=field, obj=obj)

        if field is None:
            definition = self.form
        else:
            if isinstance(field, Field):
                field = field.name
            if field in self.fields:
                definition = self.fields[field]

        if definition and permission in definition:
            allowed_roles = definition[permission]

        if callable(allowed_roles):
            allowed_roles = eval_roles(allowed_roles)

        roles = []
        for r in allowed_roles:
            if callable(r):
                r = eval_roles(r)

            if isinstance(r, (Role, str)):
                roles.append(r)
            else:
                roles.extend(r)

        security = cast("SecurityService", get_service("security"))
        return security.has_role(user, role=roles, object=obj)
