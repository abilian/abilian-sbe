# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture, mark

from abilian.core.entities import Entity
from abilian.core.models.subjects import Group, User, create_root_user
from abilian.sbe.apps.documents.models import Folder
from abilian.services.security import (
    ADMIN,
    ANONYMOUS,
    AUTHENTICATED,
    CREATOR,
    OWNER,
    READ,
    READER,
    WRITE,
    WRITER,
    Permission,
    PermissionAssignment,
    Role,
    RoleAssignment,
    SecurityAudit,
    security,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy

# from abilian.services.security.models import FolderishModel


def test_singleton() -> None:
    admin = Role("admin")
    other_admin = Role("admin")
    assert admin is other_admin
    assert id(admin) == id(other_admin)


def test_equality() -> None:
    admin = Role("admin")
    assert admin == "admin"


def test_ordering() -> None:
    roles = sorted([AUTHENTICATED, ADMIN, ANONYMOUS])
    assert roles == [ADMIN, ANONYMOUS, AUTHENTICATED]


# TODO: may fail depending on test order, due to global state
@mark.skip
def test_enumerate_assignables(db) -> None:
    assert Role.assignable_roles() == [ADMIN]


@fixture
def session(app: Application, db: SQLAlchemy) -> Iterator[Session]:
    security.start()
    create_root_user()

    yield db.session

    security.stop()
    security.clear()


class DummyModel(Entity):
    pass


def test_anonymous_user(app: Application, session: Session) -> None:
    # anonymous user is not an SQLAlchemy instance and must be handled
    # specifically to avoid tracebacks
    anon = app.login_manager.anonymous_user()
    assert not security.has_role(anon, "reader")
    assert security.has_role(anon, ANONYMOUS)
    assert security.get_roles(anon) == [ANONYMOUS]
    assert not security.has_permission(anon, "read")


def test_has_role_authenticated(app: Application, session: Session) -> None:
    anon = app.login_manager.anonymous_user()
    user = User(email="john@example.com", password="x")  # noqa: S106
    session.add(user)
    session.flush()
    assert not security.has_role(anon, AUTHENTICATED)
    assert security.has_role(user, AUTHENTICATED)


def test_root_user(session: Session) -> None:
    # Root user always has any role, any permission.
    root = User.query.get(0)
    assert isinstance(root, User)
    assert security.has_role(root, ANONYMOUS)
    assert security.has_role(root, ADMIN)
    assert security.has_permission(root, "manage")

    obj = DummyModel()
    session.add(obj)
    session.flush()
    assert security.has_role(root, ADMIN, obj)
    assert security.has_permission(root, "manage", obj)


def test_grant_basic_roles(session: Session) -> None:
    user = User(email="john@example.com", password="x")  # noqa: S106
    session.add(user)
    session.flush()

    # everybody always has role Anonymous
    assert security.has_role(user, ANONYMOUS)

    security.grant_role(user, ADMIN)
    assert security.has_role(user, ADMIN)
    assert security.get_roles(user) == [ADMIN]
    assert security.get_roles(user) == ["admin"]
    assert security.get_principals(ADMIN) == [user]

    # clear roles cache for better coverage: has_permission uses
    # _fill_role_cache_batch(), get_roles uses _fill_role_cache()
    delattr(user, "__roles_cache__")
    assert security.has_permission(user, "read")
    assert security.has_permission(user, "write")
    assert security.has_permission(user, "manage")

    security.ungrant_role(user, "admin")
    assert not security.has_role(user, "admin")
    assert security.get_roles(user) == []
    assert security.get_principals(ADMIN) == []

    assert not security.has_permission(user, "read")
    assert not security.has_permission(user, "write")
    assert not security.has_permission(user, "manage")


def test_grant_basic_roles_on_groups(session: Session) -> None:
    user = User(email="john@example.com", password="x")  # noqa: S106
    group = Group(name="Test Group")
    user.groups.add(group)
    session.add(user)
    session.flush()

    security.grant_role(group, "admin")
    assert security.has_role(group, "admin")
    assert security.get_roles(group) == ["admin"]
    assert security.get_principals(ADMIN) == [group]

    assert security.has_role(user, ADMIN)

    assert security.has_permission(user, "read")
    assert security.has_permission(user, "write")
    assert security.has_permission(user, "manage")

    security.ungrant_role(group, "admin")
    assert not security.has_role(group, "admin")
    assert security.get_roles(group) == []
    assert security.get_principals(ADMIN) == []

    assert not security.has_role(user, "admin")
    assert not security.has_permission(user, "read")
    assert not security.has_permission(user, "write")
    assert not security.has_permission(user, "manage")


def test_grant_roles_on_objects(session: Session) -> None:
    user = User(email="john@example.com", password="x")  # noqa: S106
    user2 = User(email="papa@example.com", password="p")  # noqa: S106
    group = Group(name="Test Group")
    user.groups.add(group)
    obj = DummyModel()
    session.add_all([user, user2, obj])
    session.flush()

    security.grant_role(user, "global_role")
    security.grant_role(user, "reader", obj)
    assert security.has_role(user, "reader", obj)
    assert security.get_roles(user, obj) == ["reader"]
    assert security.get_principals(READER) == []
    assert security.get_principals(READER, object=obj) == [user]

    assert security.has_permission(user, "read", obj)
    assert not security.has_permission(user, "write", obj)
    assert not security.has_permission(user, "manage", obj)

    # test get_roles "global": object roles should not appear
    assert security.get_roles(user) == ["global_role"]

    # global role is valid on all object
    assert security.has_role(user, "global_role", obj)

    security.ungrant_role(user, "reader", obj)
    assert not security.has_role(user, "reader", obj)
    assert security.get_roles(user, obj) == []
    assert security.has_role(user, "global_role", obj)

    assert not security.has_permission(user, "read", obj)
    assert not security.has_permission(user, "write", obj)
    assert not security.has_permission(user, "manage", obj)

    # owner / creator roles
    assert security.get_principals(OWNER, object=obj) == []
    assert security.get_principals(CREATOR, object=obj) == []
    old_owner = obj.owner
    old_creator = obj.creator
    obj.owner = user
    assert security.get_roles(user, obj) == [OWNER]
    assert security.get_principals(OWNER, object=obj) == [user]
    assert security.get_principals(CREATOR, object=obj) == []
    # if user2 has Admin role e gets the rights no matter Creator/Ownership
    security.grant_role(user2, ADMIN)
    assert security.has_role(user2, (OWNER, CREATOR), obj)
    assert security.has_role(user, (OWNER, CREATOR), obj)

    obj.owner = old_owner
    obj.creator = user
    assert security.get_roles(user, obj) == [CREATOR]
    assert security.get_principals(OWNER, object=obj) == []
    assert security.get_principals(CREATOR, object=obj) == [user]
    obj.creator = old_creator

    # permissions through group membership
    security.grant_role(group, "manager", obj)
    assert security.has_role(group, "manager", obj)
    assert security.get_roles(group, obj) == ["manager"]

    # group membership: user hasn't role set, but has permissions
    assert security.get_roles(user, obj, no_group_roles=True) == []
    assert security.has_permission(user, "read", obj)
    assert security.has_permission(user, "write", obj)
    assert security.has_permission(user, "manage", obj)

    group.members.remove(user)
    session.flush()
    assert not security.has_role(user, "manager", obj)
    assert security.get_roles(user, obj) == []
    assert not security.has_permission(user, "read", obj)
    assert not security.has_permission(user, "write", obj)
    assert not security.has_permission(user, "manage", obj)

    security.ungrant_role(group, "manager", obj)
    assert not security.has_role(group, "manager", obj)
    assert security.get_roles(group, obj) == []

    # when called on unmapped instance
    new_obj = DummyModel()
    assert not security.has_permission(user, READ, new_obj)


def test_grant_roles_unique(session: Session) -> None:
    user = User(email="john@example.com", password="x")  # noqa: S106
    obj = DummyModel()
    session.add_all([user, obj])
    session.flush()

    assert RoleAssignment.query.count() == 0

    security.grant_role(user, "manager", obj)
    session.flush()
    assert RoleAssignment.query.count() == 1

    security.grant_role(user, "manager", obj)
    session.flush()
    assert RoleAssignment.query.count() == 1

    security.grant_role(user, "reader", obj)
    session.flush()
    assert RoleAssignment.query.count() == 2


def test_inherit(session: Session) -> None:
    # folder = FolderishModel()
    folder = Folder()
    session.add(folder)
    session.flush()
    assert SecurityAudit.query.count() == 0

    security.set_inherit_security(folder, False)
    session.flush()
    assert not folder.inherit_security
    assert SecurityAudit.query.count() == 1

    security.set_inherit_security(folder, True)
    session.flush()
    assert folder.inherit_security
    assert SecurityAudit.query.count() == 2


def test_add_list_delete_permissions(session: Session) -> None:
    obj = DummyModel()
    assert security.get_permissions_assignments(obj) == {}
    session.add(obj)
    session.flush()

    security.add_permission(READ, AUTHENTICATED, obj)
    security.add_permission(READ, OWNER, obj)
    security.add_permission(WRITE, OWNER, obj)
    assert security.get_permissions_assignments(obj) == {
        READ: {AUTHENTICATED, OWNER},
        WRITE: {OWNER},
    }

    security.delete_permission(READ, AUTHENTICATED, obj)
    assert security.get_permissions_assignments(obj) == {READ: {OWNER}, WRITE: {OWNER}}
    assert security.get_permissions_assignments(obj, READ) == {READ: {OWNER}}

    # do it twice: it should not crash
    security.add_permission(READ, OWNER, obj)
    security.delete_permission(READ, AUTHENTICATED, obj)

    # set/get/delete global permission
    security.add_permission(READ, WRITER)
    assert security.get_permissions_assignments() == {READ: {WRITER}}


def test_has_permission_on_objects(session: Session) -> None:
    has_permission = security.has_permission
    user = User(email="john@example.com", password="x")  # noqa: S106
    group = Group(name="Test Group")
    user.groups.add(group)
    obj = DummyModel(creator=user, owner=user)
    session.add_all([user, obj])
    session.flush()

    # global role provides permissions on any object
    security.grant_role(user, READER)
    assert has_permission(user, READ, obj=obj)
    assert not has_permission(user, WRITE, obj=obj)

    security.grant_role(user, WRITER, obj=obj)
    assert has_permission(user, WRITE, obj=obj)

    # permission assignment
    security.ungrant_role(user, READER)
    security.ungrant_role(user, WRITER, object=obj)
    security.grant_role(user, AUTHENTICATED)
    assert not has_permission(user, READ, obj=obj)
    assert not has_permission(user, WRITE, obj=obj)

    pa = PermissionAssignment(role=AUTHENTICATED, permission=READ, object=obj)
    session.add(pa)
    session.flush()
    assert has_permission(user, READ, obj=obj)
    assert not has_permission(user, WRITE, obj=obj)

    session.delete(pa)
    session.flush()
    assert not has_permission(user, READ, obj=obj)

    # Owner / Creator
    for role in (OWNER, CREATOR):
        pa = PermissionAssignment(role=role, permission=READ, object=obj)
        session.add(pa)
        session.flush()
        assert has_permission(user, READ, obj=obj)

        session.delete(pa)
        session.flush()
        assert not has_permission(user, READ, obj=obj)

    # test when object is *not* in session (newly created objects have id=None
    # for instance)
    obj = DummyModel()
    assert security.has_role(user, READER, object=obj) is False


def test_has_permission_custom_roles(session: Session) -> None:
    user = User(email="john@example.com", password="x")  # noqa: S106
    session.add(user)
    session.flush()

    role = Role("custom_role")
    permission = Permission("custom permission")
    assert not security.has_permission(user, permission, roles=role)
    security.grant_role(user, role)
    assert not security.has_permission(user, permission)
    assert security.has_permission(user, permission, roles=role)

    # Permission always granted if Anonymous role
    assert security.has_permission(user, permission, roles=ANONYMOUS)

    # test convert legacy permission & implicit mapping
    security.grant_role(user, "reader")
    assert security.has_permission(user, "read")
    assert not security.has_permission(user, "write")
    assert not security.has_permission(user, "manage")

    security.grant_role(user, "writer")
    assert security.has_permission(user, "read")
    assert security.has_permission(user, "write")
    assert not security.has_permission(user, "manage")

    security.grant_role(user, "manager")
    assert security.has_permission(user, "read")
    assert security.has_permission(user, "write")
    assert security.has_permission(user, "manage")


@mark.skip
def test_query_entity_with_permission(session) -> None:
    get_filter = security.query_entity_with_permission
    user = User(email="john@example.com", password="x")  # noqa: S106
    session.add(user)

    obj_reader = DummyModel(name="reader")
    obj_writer = DummyModel(name="writer")
    obj_none = DummyModel(name="none")
    session.add_all([obj_reader, obj_writer, obj_none])

    assigments = [
        PermissionAssignment(role=READER, permission=READ, object=obj_reader),
        #
        PermissionAssignment(role=WRITER, permission=WRITE, object=obj_writer),
    ]
    session.add_all(assigments)
    session.flush()

    # very unfiltered query returns all objects
    base_query = DummyModel.query
    assert set(base_query.all()) == {obj_reader, obj_writer, obj_none}

    # user has no roles: no objects returned at all
    assert base_query.filter(get_filter(READ, user=user)).all() == []
    assert base_query.filter(get_filter(WRITE, user=user)).all() == []

    # grant object specific roles
    security.grant_role(user, READER, obj=obj_reader)
    security.grant_role(user, WRITER, obj=obj_writer)
    session.flush()
    assert base_query.filter(get_filter(READ, user=user)).all() == [obj_reader]
    assert base_query.filter(get_filter(WRITE, user=user)).all() == [obj_writer]

    # Permission granted to anonymous: objects returned
    pa = PermissionAssignment(role=ANONYMOUS, permission=WRITE, object=obj_reader)
    session.add(pa)

    assert base_query.filter(get_filter(READ, user=user)).all() == [obj_reader]
    assert set(base_query.filter(get_filter(WRITE, user=user)).all()) == {
        obj_reader,
        obj_writer,
    }
    session.delete(pa)
    assert base_query.filter(get_filter(WRITE, user=user)).all() == [obj_writer]

    # grant global roles
    security.ungrant_role(user, READER, object=obj_reader)
    security.ungrant_role(user, WRITER, object=obj_writer)
    security.grant_role(user, READER)
    security.grant_role(user, WRITER)
    session.flush()

    assert base_query.filter(get_filter(READ, user=user)).all() == [obj_reader]
    assert base_query.filter(get_filter(WRITE, user=user)).all() == [obj_writer]

    # admin role has all permissions
    # 1: local role
    security.ungrant_role(user, READER)
    security.ungrant_role(user, WRITER)
    security.grant_role(user, ADMIN, obj=obj_reader)
    security.grant_role(user, ADMIN, obj=obj_none)
    session.flush()

    assert set(base_query.filter(get_filter(READ, user=user)).all()) == {
        obj_reader,
        obj_none,
    }
    assert set(base_query.filter(get_filter(WRITE, user=user)).all()) == {
        obj_reader,
        obj_none,
    }

    # 2: global role
    security.ungrant_role(user, ADMIN, object=obj_reader)
    security.ungrant_role(user, ADMIN, object=obj_none)
    security.grant_role(user, ADMIN)
    session.flush()
    assert set(base_query.filter(get_filter(READ, user=user)).all()) == {
        obj_reader,
        obj_writer,
        obj_none,
    }

    # implicit role: Owner, Creator
    security.ungrant_role(user, ADMIN)
    assert base_query.filter(get_filter(READ, user=user)).all() == []
    assert base_query.filter(get_filter(WRITE, user=user)).all() == []

    obj_reader.creator = user
    obj_writer.owner = user
    assigments = [
        PermissionAssignment(role=CREATOR, permission=READ, object=obj_reader),
        #
        PermissionAssignment(role=OWNER, permission=WRITE, object=obj_writer),
    ]
    session.add_all(assigments)
    session.flush()

    assert base_query.filter(get_filter(READ, user=user)).all() == [obj_reader]
    assert base_query.filter(get_filter(WRITE, user=user)).all() == [obj_writer]


def test_add_delete_permissions_expunged_obj(session: Session) -> None:
    # weird case. In CreateObject based views, usually Entity is
    # instanciated and might be added to session if it has a relationship
    # with an existing object.
    # `init_object` must do `session.expunge(obj)`. But entities will
    # have initialized default permissions during `after_attach`.
    #
    # At save time, the object is added again to session. The bug is that
    # without precaution we may create permissions assignment twice, because
    # assignments created in the first place are not yet again in session
    # (new, dirty, deleted) and cannot be found with a filtered query on
    # PermissionAssignment because they have not been flushed yet.
    #
    security.add_permission(READ, OWNER, None)
    obj = DummyModel()
    # override default permission at instance level
    obj.__default_permissions__ = frozenset({(READ, frozenset({OWNER}))})
    # core.entities._setup_default_permissions creates
    session.add(obj)
    # permissions
    security.add_permission(READ, OWNER, obj)
    # no-op obj and its permissions are removed from session
    session.expunge(obj)

    session.add(obj)
    # obj in session again. When
    # _setup_default_permissions is called during
    # `after_flush`, previously created permission are not
    # yet back in session. The cascading rule will add
    # them just after (as of sqlalchemy 0.8, at least)

    # Finally the test! IntegrityError will be raised if we have done
    # something wrong (`Key (permission, role, object_id)=(..., ..., ...)
    # already exists`)
    session.flush()
