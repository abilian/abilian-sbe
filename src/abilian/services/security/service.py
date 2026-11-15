# Copyright (c) 2012-2024, Abilian SAS

"""Security service, manages roles and permissions."""

from __future__ import annotations

from functools import wraps
from itertools import chain
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy import sql
from sqlalchemy.orm import Session, object_session, subqueryload

from abilian.core.context import get_current_principal
from abilian.core.entities import Entity
from abilian.core.extensions import db
from abilian.core.models.subjects import ROOT_USER_ID, Group, Principal, User
from abilian.core.util import unwrap
from abilian.services import Service, ServiceState
from abilian.services.security.models import (
    ADMIN,
    ANONYMOUS,
    AUTHENTICATED,
    CREATE,
    CREATOR,
    DELETE,
    MANAGE,
    MANAGER,
    OWNER,
    PERMISSIONS_ATTR,
    READ,
    READER,
    WRITE,
    WRITER,
    FolderishModel,
    InheritSecurity,
    Permission,
    PermissionAssignment,
    Role,
    RoleAssignment,
    SecurityAudit,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence

    from sqlalchemy.sql.selectable import Exists

    from abilian.app import Application
    from abilian.core.extensions.login import AnonymousUser
    from abilian.core.models import Model


#: list of legacy supported permissions when not using :class:`Permission`
#: instance
PERMISSIONS = frozenset(["read", "write", "manage"])

__all__ = [
    "InheritSecurity",
    "SecurityAudit",
    "SecurityError",
    "SecurityService",
    "security",
]

#: default security matrix
DEFAULT_PERMISSION_ROLE: dict[Permission, frozenset[Role]] = {}
prm = DEFAULT_PERMISSION_ROLE
prm[MANAGE] = frozenset({ADMIN, MANAGER})
prm[WRITE] = frozenset({ADMIN, MANAGER, WRITER})
prm[CREATE] = frozenset({ADMIN, MANAGER, WRITER})
prm[DELETE] = frozenset({ADMIN, MANAGER, WRITER})
prm[READ] = frozenset({ADMIN, MANAGER, WRITER, READER})
del prm


class SecurityError(Exception):
    pass


class SecurityServiceState(ServiceState):
    use_cache = True
    #: True if security has changed
    needs_db_flush = False


def require_flush(fun: Callable) -> Callable:
    """Decorator for methods that need to query security.

    It ensures all security related operations are flushed to DB, but
    avoids unneeded flushes.
    """

    @wraps(fun)
    def ensure_flushed(service: SecurityService, *args: Any, **kwargs: Any) -> Any:
        if service.app_state.needs_db_flush:
            session = db.session()
            if not session._flushing and any(
                isinstance(m, (RoleAssignment, SecurityAudit))
                for models in (session.new, session.dirty, session.deleted)
                for m in models
            ):
                session.flush()
            service.app_state.needs_db_flush = False

        return fun(service, *args, **kwargs)

    return ensure_flushed


def query_pa_no_flush(
    session: Session, permission: Permission, role: Role, obj: Model | None
):
    """Query for a :class:`PermissionAssignment` using `session` without any
    `flush()`.

    It works by looking in session `new`, `dirty` and `deleted`, and issuing a
    query with no autoflush.

    .. note::

        This function is used by `add_permission` and `delete_permission` to allow
        to add/remove the same assignment twice without issuing any flush. Since
        :class:`Entity` creates its initial permissions in during
        :sqlalchemy:`sqlalchemy.orm.events.SessionEvents.after_attach`, it might be
        problematic to issue a flush when entity is not yet ready to be flushed
        (missing required attributes for example).
    """
    to_visit = [session.deleted, session.dirty, session.new]
    with session.no_autoflush:
        # no_autoflush is required to visit PERMISSIONS_ATTR without emitting a
        # flush()
        if obj:
            to_visit.append(getattr(obj, PERMISSIONS_ATTR))

        permissions = (
            p for p in chain(*to_visit) if isinstance(p, PermissionAssignment)
        )

        for instance in permissions:
            if (
                instance.permission == permission
                and instance.role == role
                and instance.object == obj
            ):
                return instance

        # Last chance: perform a filtered query. If obj is not None, sometimes
        # getattr(obj, PERMISSIONS_ATTR) has objects not present in session
        # not in this query (maybe in a parent session transaction `new`?).
        if obj is not None and obj.id is None:
            obj = None

        return (
            session.query(PermissionAssignment)
            .filter(
                PermissionAssignment.permission == permission,
                PermissionAssignment.role == role,
                PermissionAssignment.object == obj,
            )
            .first()
        )


class SecurityService(Service):
    name = "security"
    AppStateClass = SecurityServiceState

    def init_app(self, app: Application) -> None:
        super().init_app(app)
        state = app.extensions[self.name]
        state.use_cache = True

    def _needs_flush(self) -> None:
        """Mark next security queries needs DB flush to have up to date
        information."""
        self.app_state.needs_db_flush = True

    def clear(self) -> None:
        pass

    def _current_user_manager(self, session: Session | None = None) -> User | None:
        """Who is performing this change, for the security audit trail.

        Falls back to the SYSTEM principal, so that a grant made by a
        migration or the CLI is still attributed to something -- that is what
        this did before, and changing it would silently rewrite what the audit
        trail records.

        SYSTEM does not always exist: it is created by `flask initdb`, not by
        `create_all`. `None` is the honest answer then, and
        `SecurityAudit.manager_id` is nullable to allow it -- which is how the
        admin audit panel came to meet a null manager and raise on it.
        """
        if session is None:
            session = db.session()

        user = get_current_principal()
        if user is None:
            return session.query(User).get(ROOT_USER_ID)

        if sa.orm.object_session(user) is not session:
            # this can happen when called from a task during development
            # (with CELERY_ALWAYS_EAGER=True): the task SA session is not
            # app.db.session, and we should not attach this object to
            # the other session, because it can make weird, hard-to-debug
            # errors related to session.identity_map.
            return session.query(User).get(user.id)
        return user

    # security log
    @require_flush
    def entries_for(self, obj, limit=20):
        assert isinstance(obj, Entity)
        return (
            SecurityAudit.query.filter(SecurityAudit.object == obj)
            .order_by(SecurityAudit.happened_at.desc())
            .limit(limit)
        )

    # inheritance
    def set_inherit_security(self, obj: FolderishModel, inherit_security: bool) -> None:
        assert isinstance(obj, InheritSecurity)
        assert isinstance(obj, Entity)

        obj.inherit_security = inherit_security
        session = object_session(obj) if obj is not None else db.session()
        session.add(obj)

        manager = self._current_user_manager(session=session)
        op = (
            SecurityAudit.SET_INHERIT
            if inherit_security
            else SecurityAudit.UNSET_INHERIT
        )
        audit = SecurityAudit(
            manager=manager,
            op=op,
            object=obj,
            object_id=obj.id,
            object_type=obj.entity_type,
            object_name=obj.name,
        )
        session.add(audit)
        self._needs_flush()

    #
    # Roles-related API.
    #
    @require_flush
    def get_roles(
        self,
        principal: AnonymousUser | Group | User,
        object: Model | None = None,
        no_group_roles: bool = False,
    ) -> list[Role]:
        """Get all the roles attached to given `principal`, on a given
        `object`.

        :param principal: a :class:`User` or :class:`Group`

        :param object: an :class:`Entity`

        :param no_group_roles: If `True`, return only direct roles, not roles
        acquired through group membership.
        """
        assert principal
        if hasattr(principal, "is_anonymous") and principal.is_anonymous:
            return [ANONYMOUS]

        query = db.session.query(RoleAssignment.role)
        if isinstance(principal, Group):
            filter_principal = RoleAssignment.group == principal
        else:
            filter_principal = RoleAssignment.user == principal
            if not no_group_roles:
                groups = [g.id for g in principal.groups]
                if groups:
                    filter_principal |= RoleAssignment.group_id.in_(groups)

        query = query.filter(filter_principal)

        if object is not None:
            assert isinstance(object, Entity)

        query = query.filter(RoleAssignment.object == object)
        roles = {i[0] for i in query.all()}

        if object is not None:
            for attr, role in (("creator", CREATOR), ("owner", OWNER)):
                if getattr(object, attr) == principal:
                    roles.add(role)
        return list(roles)

    @require_flush
    def get_principals(
        self,
        role: Role,
        *,
        anonymous: bool = True,
        users: bool = True,
        groups: bool = True,
        object: Model | None = None,
        as_list: bool = True,
    ) -> Collection[Principal]:
        """Return all users which are assigned given role."""
        if not isinstance(role, Role):
            role = Role(role)
        assert role
        assert users or groups
        query = RoleAssignment.query.filter_by(role=role)

        if not anonymous:
            query = query.filter(RoleAssignment.anonymous == False)
        if not users:
            query = query.filter(RoleAssignment.user == None)
        elif not groups:
            query = query.filter(RoleAssignment.group == None)

        query = query.filter(RoleAssignment.object == object)
        principals = {(ra.user or ra.group) for ra in query.all()}

        if object is not None and role in (CREATOR, OWNER):
            p = object.creator if role == CREATOR else object.owner
            if p:
                principals.add(p)

        if not as_list:
            return principals

        return list(principals)

    @require_flush
    def _all_roles(self, principal: Principal) -> dict[str | None, set[Role]]:
        query = (
            db.session.query(RoleAssignment.object_id, RoleAssignment.role)
            .outerjoin(Entity)
            .add_columns(Entity._entity_type)
        )

        if isinstance(principal, User):
            filter_cond = RoleAssignment.user == principal
            if principal.groups:
                group_ids = (g.id for g in principal.groups)
                filter_cond |= RoleAssignment.group_id.in_(group_ids)

            query = query.filter(filter_cond)
        else:
            query = query.filter(RoleAssignment.group == principal)

        results = query.all()
        all_roles = {}
        for object_id, role, object_type in results:
            if object_id is None:
                object_key = None
            else:
                object_key = f"{object_type}:{object_id}"
            all_roles.setdefault(object_key, set()).add(role)

        return all_roles

    def _role_cache(self, principal: Principal) -> dict[str | None, set[Role]]:
        if not self._has_role_cache(principal):
            # FIXME: should call _fill_role_cache?
            principal.__roles_cache__ = {}

        return principal.__roles_cache__

    def _has_role_cache(self, principal: Principal) -> bool:
        return hasattr(principal, "__roles_cache__")

    def _set_role_cache(
        self, principal: Principal, cache: dict[str | None, set[Role]]
    ) -> None:
        principal.__roles_cache__ = cache

    def _fill_role_cache(
        self, principal: Principal, overwrite: bool = False
    ) -> dict[str | None, set[Role]]:
        """Fill role cache for `principal` (User or Group), in order to avoid
        too many queries when checking role access with 'has_role'.

        Return role_cache of `principal`
        """
        if not self.app_state.use_cache:
            return {}

        if not self._has_role_cache(principal) or overwrite:
            self._set_role_cache(principal, self._all_roles(principal))
        return self._role_cache(principal)

    @require_flush
    def _fill_role_cache_batch(
        self, principals: Collection[Principal], overwrite: bool = False
    ) -> None:
        """Fill role cache for `principals` (Users and/or Groups), in order to
        avoid too many queries when checking role access with 'has_role'."""
        if not self.app_state.use_cache:
            return

        query = db.session.query(RoleAssignment)
        users = {u for u in principals if isinstance(u, User)}
        groups = {g for g in principals if isinstance(g, Group)}
        groups |= {g for u in users for g in u.groups}

        if not overwrite:
            users = {u for u in users if not self._has_role_cache(u)}
            groups = {g for g in groups if not self._has_role_cache(g)}

        if not (users or groups):
            return

        # ensure principals processed here will have role cache. Thus users or
        # groups without any role will have an empty role cache, to avoid
        # unneeded individual DB query when calling self._fill_role_cache(p).
        for p in chain(users, groups):
            self._set_role_cache(p, {})

        filter_cond = []
        if users:
            filter_cond.append(RoleAssignment.user_id.in_(u.id for u in users))
        if groups:
            filter_cond.append(RoleAssignment.group_id.in_(g.id for g in groups))

        query = query.filter(sql.or_(*filter_cond))
        ra_users: dict[User, dict[str, set[Role]]] = {}
        ra_groups: dict[Group, dict[str, set[Role]]] = {}
        for ra in query.all():
            if ra.user:
                all_roles = ra_users.setdefault(ra.user, {})
            else:
                all_roles = ra_groups.setdefault(ra.group, {})

            object_key = (
                f"{ra.object.entity_type}:{ra.object_id:d}"
                if ra.object is not None
                else None
            )
            all_roles.setdefault(object_key, set()).add(ra.role)

        for group, all_roles in ra_groups.items():
            self._set_role_cache(group, all_roles)

        for user, all_roles in ra_users.items():
            for gr in user.groups:
                group_roles = self._fill_role_cache(gr)
                for object_key, roles in group_roles.items():
                    obj_roles = all_roles.setdefault(object_key, set())
                    obj_roles |= roles

            self._set_role_cache(user, all_roles)

    def _clear_role_cache(self, principal: Principal) -> None:
        if hasattr(principal, "__roles_cache__"):
            del principal.__roles_cache__

        if isinstance(principal, Group):
            for u in principal.members:
                if hasattr(u, "__roles_cache__"):
                    del u.__roles_cache__

    def has_role(
        self,
        principal: Principal | Role | None,
        role: Collection[Role] | Role | str,
        object: Model | None = None,
    ) -> bool:
        """True if `principal` has `role` (either globally, if `object` is
        None, or on the specific `object`).

        :param:role: can be a list or tuple of strings or a :class:`Role`
            instance

        `object` can be an :class:`Entity`, a string, or `None`.

        Note: we're using a cache for efficiency here. TODO: check that we're not
        over-caching.

        Note2: caching could also be moved upfront to when the user is loaded.
        """
        if not principal:
            return False

        principal = unwrap(principal)

        if isinstance(role, (Role, (str,))):
            role = (role,)

        # admin & manager always have role
        valid_roles = frozenset((ADMIN, MANAGER, *tuple(role)))

        if ANONYMOUS in valid_roles:
            # everybody has the role 'Anonymous'
            return True

        if (
            AUTHENTICATED in valid_roles
            and isinstance(principal, User)
            and not principal.is_anonymous
        ):
            return True

        if principal is ANONYMOUS or (
            hasattr(principal, "is_anonymous") and principal.is_anonymous
        ):
            # anonymous user, and anonymous role isn't in valid_roles
            return False

        # root always have any role
        if isinstance(principal, User) and principal.id == 0:
            return True

        if object:
            assert isinstance(object, Entity)
            object_key = f"{object.object_type}:{object.id!s}"
            if CREATOR in role:
                if object.creator == principal:
                    return True
            if OWNER in role:
                if object.owner == principal:
                    return True

        else:
            object_key = None

        all_roles = (
            self._fill_role_cache(principal)
            if self.app_state.use_cache
            else self._all_roles(principal)
        )
        roles = set()
        roles |= all_roles.get(None, set())
        roles |= all_roles.get(object_key, set())
        return len(valid_roles & roles) > 0

    def grant_role(
        self, principal: Principal, role: Role | str, obj: Model | None = None
    ) -> None:
        """Grant `role` to `user` (either globally, if `obj` is None, or on the
        specific `obj`)."""
        assert principal

        principal = unwrap(principal)
        session = object_session(obj) if obj is not None else db.session()
        manager = self._current_user_manager(session=session)
        args = {
            "role": role,
            "object": obj,
            "anonymous": False,
            "user": None,
            "group": None,
        }

        if principal is ANONYMOUS or (
            hasattr(principal, "is_anonymous") and principal.is_anonymous
        ):
            args["anonymous"] = True
        elif isinstance(principal, User):
            args["user"] = principal
        else:
            args["group"] = principal

        query = session.query(RoleAssignment)
        if query.filter_by(**args).limit(1).count():
            # role already granted, nothing to do
            return

        # same as above but in current, not yet flushed objects in session. We
        # cannot call flush() in grant_role() since this method may be called a
        # great number of times in the same transaction, and sqlalchemy limits
        # to 100 flushes before triggering a warning
        for ra in (
            o
            for models in (session.new, session.dirty)
            for o in models
            if isinstance(o, RoleAssignment)
        ):
            if all(getattr(ra, attr) == val for attr, val in args.items()):
                return

        ra = RoleAssignment(**args)
        session.add(ra)
        audit = SecurityAudit(manager=manager, op=SecurityAudit.GRANT, **args)
        if obj is not None:
            audit.object_id = obj.id
            audit.object_type = obj.entity_type
            object_name = ""
            for attr_name in ("name", "path", "__path_before_delete"):
                if hasattr(obj, attr_name):
                    object_name = getattr(obj, attr_name)
            audit.object_name = object_name

        session.add(audit)
        self._needs_flush()

        if hasattr(principal, "__roles_cache__"):
            del principal.__roles_cache__

    def ungrant_role(
        self, principal: Principal, role: Role | str, object: Model | None = None
    ) -> None:
        """Ungrant `role` to `user` (either globally, if `object` is None, or
        on the specific `object`)."""

        assert principal
        principal = unwrap(principal)
        session = object_session(object) if object is not None else db.session()
        manager = self._current_user_manager(session=session)

        args = {
            "role": role,
            "object": object,
            "anonymous": False,
            "user": None,
            "group": None,
        }
        query = session.query(RoleAssignment)
        query = query.filter(
            RoleAssignment.role == role, RoleAssignment.object == object
        )

        if principal is ANONYMOUS or (
            hasattr(principal, "is_anonymous") and principal.is_anonymous
        ):
            args["anonymous"] = True
            query.filter(
                RoleAssignment.anonymous == False,
                RoleAssignment.user == None,
                RoleAssignment.group == None,
            )

        elif isinstance(principal, User):
            args["user"] = principal
            query = query.filter(RoleAssignment.user == principal)
        else:
            args["group"] = principal
            query = query.filter(RoleAssignment.group == principal)

        ra = query.one()
        session.delete(ra)
        audit = SecurityAudit(manager=manager, op=SecurityAudit.REVOKE, **args)
        session.add(audit)
        self._needs_flush()
        self._clear_role_cache(principal)

    @require_flush
    def get_role_assignements(self, obj: Model) -> list:
        session = object_session(obj) if obj is not None else db.session()
        if not session:
            session = db.session()
        query = session.query(RoleAssignment)
        query = query.filter(RoleAssignment.object == obj).options(
            subqueryload(RoleAssignment.user).subqueryload(User.groups)
        )

        role_assignments = query.all()

        results = []
        for ra in role_assignments:
            if ra.anonymous:
                principal = ANONYMOUS
            elif ra.user:
                principal = ra.user
            else:
                principal = ra.group
            results.append((principal, ra.role))
        return results

    #
    # Permission API, currently hardcoded
    #
    def has_permission(
        self,
        user: User,
        permission: Permission | str,
        obj: Model | None = None,
        inherit: bool = False,
        roles: Role | str | list[Role | str] | None = None,
    ) -> bool:
        """
        :param obj: target object to check permissions.
        :param inherit: check with permission inheritance. By default, check only
                        local roles.
        :param roles: additional valid role or iterable of roles having
                      `permission`.
        """
        if not isinstance(permission, Permission):
            assert permission in PERMISSIONS
            permission = Permission(permission)
        user = unwrap(user)

        session = None
        if obj is not None:
            session = object_session(obj)

        if session is None:
            session = db.session()

        # root always have any permission
        if isinstance(user, User) and user.id == 0:
            return True

        # valid roles
        # 1: from database
        pa_filter = PermissionAssignment.object == None
        if obj is not None and obj.id is not None:
            pa_filter |= PermissionAssignment.object == obj

        pa_filter &= PermissionAssignment.permission == permission
        valid_roles = session.query(PermissionAssignment.role).filter(pa_filter)
        valid_roles = {res[0] for res in valid_roles.yield_per(1000)}

        # complete with defaults
        valid_roles |= {ADMIN}  # always have all permissions
        valid_roles |= DEFAULT_PERMISSION_ROLE.get(permission, set())

        # FIXME: obj.__class__ could define default permisssion matrix too

        if roles is not None:
            if isinstance(roles, (Role, str)):
                roles = (roles,)

            for r in roles:
                valid_roles.add(Role(r))

        # FIXME: query permission_role: global and on object

        if ANONYMOUS in valid_roles:
            return True

        if AUTHENTICATED in valid_roles and not user.is_anonymous:
            return True

        # first test global roles, then object local roles
        checked_objs = [None, obj]
        # An object that is not an InheritSecurity has no chain to walk, which
        # is an answer rather than a caller's mistake: `inherit=True` asks to
        # follow the chain where there is one. This used to dereference
        # `obj.inherit_security` regardless and raise AttributeError -- a
        # Community, say, has no such attribute.
        if inherit and isinstance(obj, InheritSecurity):
            while obj.inherit_security and obj.parent is not None:
                obj = obj.parent
                checked_objs.append(obj)

        principals = [user, *list(user.groups)]
        self._fill_role_cache_batch(principals)

        return any(
            self.has_role(principal, valid_roles, item)
            for principal in principals
            for item in checked_objs
        )

    def query_entity_with_permission(
        self,
        permission: Permission,
        user: User | None = None,
        Model: type[Model] = Entity,
    ) -> Exists:
        """Filter a query on an :class:`Entity` or on of its subclasses.

        Usage::

            read_q = security.query_entity_with_permission(READ, Model=MyModel)
            MyModel.query.filter(read_q)

        It should always be placed before any `.join()` happens in the query; else
        sqlalchemy might join to the "wrong" entity table when joining to other
        :class:`Entity`.

        :param user: user to filter for. Default: `current_user`.

        :param permission: required :class:`Permission`

        :param Model: An :class:`Entity` based class. Useful when there is more than
        one Entity based object in query, or if an alias should be used.

        :returns: a `sqlalchemy.sql.exists()` expression.
        """
        assert isinstance(permission, Permission)
        assert issubclass(Model, Entity)
        RA = sa.orm.aliased(RoleAssignment)
        PA = sa.orm.aliased(PermissionAssignment)
        # id column from entity table. Model.id would refer to 'model' table.
        # this allows the DB to use indexes / foreign key constraints.
        id_column = sa.inspect(Model).primary_key[0]
        creator = Model.creator
        owner = Model.owner

        if user is None:
            user = get_current_principal()

        # build role CTE
        principal_filter = RA.anonymous == True

        if user is not None and not user.is_anonymous:
            principal_filter |= RA.user == user

        if user is not None and user.groups:
            principal_filter |= RA.group_id.in_([grp.id for grp in user.groups])

        RA = sa.sql.select(RA).where(principal_filter).cte()
        permission_exists = sa.sql.exists().where(
            sa.sql.and_(
                PA.permission == permission,
                PA.object_id == id_column,
                (RA.c.role == PA.role) | (PA.role == ANONYMOUS),
                (RA.c.object_id == PA.object_id) | (RA.c.object_id == None),
            )
        )

        # is_admin: self-explanatory. It search for local or global admin
        # role, but PermissionAssignment is not involved, thus it can match on
        # entities that don't have *any permission assignment*, whereas previous
        # expressions cannot.
        is_admin = sa.sql.exists().where(
            sa.sql.and_(
                RA.c.role == ADMIN,
                (RA.c.object_id == id_column) | (RA.c.object_id == None),
                principal_filter,
            )
        )

        filter_expr = permission_exists | is_admin

        if user and not user.is_anonymous:
            is_owner_or_creator = sa.sql.exists().where(
                sa.sql.and_(
                    PA.permission == permission,
                    PA.object_id == id_column,
                    sa.sql.or_(
                        (PA.role == OWNER) & (owner == user),
                        (PA.role == CREATOR) & (creator == user),
                    ),
                )
            )
            filter_expr |= is_owner_or_creator

        return filter_expr

    def get_permissions_assignments(
        self, obj: Model | None = None, permission: Permission | None = None
    ) -> dict[Permission, set[Role]]:
        """
        :param permission: return only roles having this permission

        :returns: an dict where keys are `permissions` and values `roles` iterable.
        """
        session = None
        if obj is not None:
            assert isinstance(obj, Entity)
            session = object_session(obj)

            if obj.id is None:
                obj = None

        if session is None:
            session = db.session()

        pa = session.query(
            PermissionAssignment.permission, PermissionAssignment.role
        ).filter(PermissionAssignment.object == obj)

        if permission:
            pa = pa.filter(PermissionAssignment.permission == permission)

        results: dict[Permission, set[Role]] = {}
        for perm, role in pa.yield_per(1000):
            results.setdefault(perm, set()).add(role)

        return results

    def add_permission(
        self, permission: Permission, role: Role, obj: Model | None = None
    ) -> None:
        session = None
        if obj is not None:
            session = object_session(obj)

        if session is None:
            session = db.session()

        pa = query_pa_no_flush(session, permission, role, obj)

        if not pa:
            pa = PermissionAssignment(permission=permission, role=role, object=obj)

        # do it in any case: it could have been found in session.deleted
        session.add(pa)

    def delete_permission(
        self, permission: Permission, role: Role, obj: Model | None = None
    ) -> None:
        session = None
        if obj is not None:
            session = object_session(obj)

        if session is None:
            session = db.session()

        pa = query_pa_no_flush(session, permission, role, obj)

        if pa:
            session.delete(pa)
            if obj:
                # this seems to be required with sqlalchemy > 0.9
                session.expire(obj, [PERMISSIONS_ATTR])

    def filter_with_permission(
        self,
        user: User,
        permission: Permission | str,
        obj_list: Sequence[Model],
        inherit=False,
    ):
        user = unwrap(user)
        return [
            obj
            for obj in obj_list
            if self.has_permission(user, permission, obj, inherit)
        ]


# Instanciate the service
security = SecurityService()


def is_site_admin(user: User | None = None) -> bool:
    """Does `user` hold a site-wide administrative role?

    True for ADMIN and for the site-wide MANAGER role: `has_role` seeds its
    `valid_roles` with both, so either one answers True to any role asked
    about. Which also makes the two-call form redundant -- `has_role(u, ADMIN)
    or has_role(u, MANAGER)`, as AuthService used to compute, is the first call
    twice.

    Deliberately *not* the same question as `communities.security.can_manage`,
    which asks about one community. Both used to be written to `g.is_manager`,
    by two different producers, and read by seven call sites that could not tell
    which of the two they had got.
    """
    if user is None:
        user = get_current_principal()
    if user is None or user.is_anonymous:
        return False
    return security.has_role(user, ADMIN)
