# Copyright (c) 2012-2024, Abilian SAS

"""An attachment's permissions are its owner's.

The attachment routes checked nothing: only that the entity existed and
supported attachments. `ObjectView.permission` goes to the *form*, to decide
which fields render, and is not an access check; the blueprint is an
`AccessControlBlueprint` built with no `allowed_roles`, so it registers no
controller and the default policy admits any authenticated user. The
capabilities that would have answered correctly sat on `AttachmentsManager`,
consulted only by a template the app never renders.

Unreachable today, because no model is registered attachable -- which is
exactly why it needed closing rather than noting: the day someone registers
one, for reasons of their own, the routes arrive already open. This module
registers one, so the check is exercised.

See notes/plan-attachments.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, UnicodeText

from abilian.core.entities import Entity
from abilian.core.models import attachment
from abilian.core.models.blob import Blob
from abilian.core.models.subjects import User
from abilian.services import security_service
from abilian.services.security import READ, WRITE
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


@attachment.register
class AttachableThing(Entity):
    """The only attachable model in the codebase, and it is a fixture."""

    __tablename__ = "test_attachable_thing"

    note = Column(UnicodeText, default="")


def _user(db: SQLAlchemy, email: str) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    return user


def _thing_with_attachment(db: SQLAlchemy):
    thing = AttachableThing(name="A thing")
    db.session.add(thing)
    db.session.flush()

    att = attachment.Attachment(name="note.txt", entity=thing)
    att.blob = Blob(b"hello")
    db.session.add(att)
    db.session.commit()
    return thing, att


def test_a_user_without_read_cannot_download(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    ensure_services_started(["security"])
    thing, att = _thing_with_attachment(db)
    stranger = _user(db, "stranger@example.com")
    db.session.commit()

    with client_login(client, stranger):
        response = client.get(
            f"/attachments/{thing.id}/{att.id}/download", follow_redirects=False
        )

    assert response.status_code == 403


def test_read_on_the_owner_is_enough_to_download(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    ensure_services_started(["security"])
    thing, att = _thing_with_attachment(db)
    reader = _user(db, "reader@example.com")
    security_service.grant_role(reader, "reader", thing)
    db.session.commit()

    with client_login(client, reader):
        response = client.get(f"/attachments/{thing.id}/{att.id}/download")

    assert response.status_code == 200
    assert response.data == b"hello"


def test_read_is_not_enough_to_delete(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    """The escalation the missing checks allowed: any authenticated user could
    delete an attachment on any entity."""
    ensure_services_started(["security"])
    thing, att = _thing_with_attachment(db)
    reader = _user(db, "reader@example.com")
    security_service.grant_role(reader, "reader", thing)
    db.session.commit()

    with client_login(client, reader):
        response = client.get(f"/attachments/{thing.id}/{att.id}/delete")

    assert response.status_code == 403


def test_the_owner_permissions_are_what_is_asked(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    """Not the attachment's own -- an attachment has no separate access rule.

    The capabilities read `current_user` rather than taking a subject, so this
    needs a logged-in request to ask them at all. That is the ambient-argument
    problem plan-authorization.md is about, in a module it has not reached.
    """
    ensure_services_started(["security"])
    thing, _att = _thing_with_attachment(db)
    writer = _user(db, "writer@example.com")
    security_service.grant_role(writer, "writer", thing)
    db.session.commit()

    assert security_service.has_permission(writer, READ, thing)
    assert security_service.has_permission(writer, WRITE, thing)

    with client_login(client, writer), app.test_request_context("/"):
        from flask import g

        g.user = writer
        manager = app.extensions["attachments"].manager(thing)
        assert manager.can_read(thing)
        assert manager.can_write(thing)
