# Copyright (c) 2012-2024, Abilian SAS

"""Step 3 moved four ambient reads onto one accessor. This pins what each of
them did before, so the move is checkable rather than asserted.

The four:

- `OwnedMixin.__init__`          `g.user` in `except (RuntimeError, AttributeError)`
- `_current_user_manager`        `g.user` in `except Exception`, else `User.get(0)`
- `query_entity_with_permission` `unwrap(current_user)`
- `is_site_admin`                `current_user`

One of them was not equivalent, and this file is how that was found: attributing
an audit entry made outside a request. It used to be the SYSTEM principal and
had become null.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture

from abilian.core.models.subjects import ROOT_USER_ID, User, create_root_user
from abilian.sbe.apps.documents.models import Document
from abilian.services.security import ADMIN, is_site_admin, security
from abilian.services.security.models import SecurityAudit
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


@fixture
def actor(db: SQLAlchemy) -> User:
    user = User(email="actor@example.com", can_login=True)
    db.session.add(user)
    db.session.flush()
    return user


# --- OwnedMixin: who a new entity is attributed to ---------------------------


def test_an_entity_made_with_nobody_acting_has_no_creator(
    app: Application, db: SQLAlchemy
) -> None:
    """A migration, a task or the CLI creates entities with no acting user.

    The old code reached this by letting `g.user` raise and swallowing it.
    """
    with app.app_context():
        doc = Document(name="from-a-task.txt")

    assert doc.creator is None
    assert doc.owner is None


def test_an_entity_is_attributed_to_the_acting_user(
    app: Application, actor: User
) -> None:
    with app.test_request_context("/"):
        from flask import g

        g.user = actor
        doc = Document(name="from-a-request.txt")

    assert doc.creator is actor
    assert doc.owner is actor


def test_an_explicit_creator_is_not_overwritten(
    app: Application, actor: User, db: SQLAlchemy
) -> None:
    other = User(email="other@example.com", can_login=True)
    db.session.add(other)
    db.session.flush()

    with app.test_request_context("/"):
        from flask import g

        g.user = actor
        doc = Document(name="explicit.txt", creator=other)

    assert doc.creator is other, "an explicit creator must win over the actor"


# --- the security audit trail's manager --------------------------------------


def test_a_grant_outside_a_request_is_attributed_to_system(
    app: Application, db: SQLAlchemy, actor: User
) -> None:
    """The regression this file was written to catch.

    `flask initdb` creates SYSTEM, so on a real instance this path had a
    manager; step 3 briefly made it null, silently changing what the audit
    trail records.
    """
    ensure_services_started(["security"])
    create_root_user()

    security.grant_role(actor, ADMIN)
    db.session.flush()

    entry = db.session.query(SecurityAudit).order_by(SecurityAudit.id.desc()).first()
    assert entry.manager is not None
    assert entry.manager.id == ROOT_USER_ID


def test_a_grant_is_attributed_to_whoever_made_it(
    app: Application, db: SQLAlchemy, actor: User
) -> None:
    ensure_services_started(["security"])
    create_root_user()
    target = User(email="target@example.com", can_login=True)
    db.session.add(target)
    db.session.flush()

    with app.test_request_context("/"):
        from flask import g

        g.user = actor
        security.grant_role(target, ADMIN)
        db.session.flush()

    entry = db.session.query(SecurityAudit).order_by(SecurityAudit.id.desc()).first()
    assert entry.manager is actor


def test_no_system_user_is_tolerated(
    app: Application, db: SQLAlchemy, actor: User
) -> None:
    """SYSTEM comes from `flask initdb`, not `create_all`, so it is often
    absent -- which is why `manager_id` is nullable and why the audit panel
    has to render a null actor."""
    ensure_services_started(["security"])
    assert db.session.query(User).get(ROOT_USER_ID) is None

    security.grant_role(actor, ADMIN)
    db.session.flush()

    entry = db.session.query(SecurityAudit).order_by(SecurityAudit.id.desc()).first()
    assert entry.manager is None


# --- is_site_admin, with nobody acting ---------------------------------------


def test_is_site_admin_is_false_with_nobody_acting(app: Application) -> None:
    ensure_services_started(["security"])

    with app.app_context():
        assert is_site_admin() is False

    with app.test_request_context("/"):
        assert is_site_admin() is False


# --- inheritance asked of an object that has none ----------------------------


def test_inherit_on_an_object_without_a_chain(
    app: Application, db: SQLAlchemy, actor: User, community1
) -> None:
    """`inherit=True` follows the chain where there is one, and there is not
    always one. This used to dereference `obj.inherit_security` regardless and
    raise AttributeError on anything that is not an InheritSecurity -- harmless
    while the only caller passing it was the content repository, which only
    passes folderish content, and a trap for anything computing permissions
    over arbitrary objects."""
    ensure_services_started(["security"])

    assert security.has_permission(actor, "manage", community1, inherit=True) is False
