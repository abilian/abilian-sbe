# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.core.entities import Entity
from abilian.services import get_security_service, security

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session

    from abilian.core.sqlalchemy import SQLAlchemy


def test_default_permissions(app: Flask, db: SQLAlchemy, session: Session) -> None:
    class MyRestrictedType(Entity):
        __default_permissions__ = {
            security.READ: {security.ANONYMOUS},
            security.WRITE: {security.OWNER},
            security.CREATE: {security.WRITER},
            security.DELETE: {security.OWNER},
        }

    assert isinstance(MyRestrictedType.__default_permissions__, frozenset)

    expected = frozenset(
        {
            (security.READ, frozenset({security.ANONYMOUS})),
            #
            (security.WRITE, frozenset({security.OWNER})),
            #
            (security.CREATE, frozenset({security.WRITER})),
            #
            (security.DELETE, frozenset({security.OWNER})),
        }
    )
    assert MyRestrictedType.__default_permissions__ == expected

    db.create_all()  # create missing 'mytype' table

    obj = MyRestrictedType(name="test object")
    session.add(obj)
    PA = security.PermissionAssignment
    query = session.query(PA.role).filter(PA.object == obj)

    assert query.filter(PA.permission == security.READ).all() == [(security.ANONYMOUS,)]
    assert query.filter(PA.permission == security.WRITE).all() == [(security.OWNER,)]
    assert query.filter(PA.permission == security.DELETE).all() == [(security.OWNER,)]

    # special case:
    assert query.filter(PA.permission == security.CREATE).all() == []

    security_svc = get_security_service()
    permissions = security_svc.get_permissions_assignments(obj)
    assert permissions == {
        security.READ: {security.ANONYMOUS},
        security.WRITE: {security.OWNER},
        security.DELETE: {security.OWNER},
    }
