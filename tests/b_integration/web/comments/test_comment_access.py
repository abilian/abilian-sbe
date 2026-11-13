# Copyright (c) 2012-2024, Abilian SAS

"""A comment's permissions are its entity's, plus its author's own.

The rule -- "whoever owns this comment, or a site admin" -- was written twice
in `macros/comment.html` and nowhere else. The views checked only that the
entity existed and was commentable, and the blueprint is an
`AccessControlBlueprint` with no `allowed_roles`, so every route was open to
any authenticated user. Unreachable today because no model is registered
commentable, which is the same reason and the same shape as the attachment
routes; see notes/plan-attachments.md.

The rule is now asked of the engine rather than spelled out: `OWNER` is a real
role and `has_role` answers it against `object.owner`, so passing it to
`has_permission` as an additional valid role says "whoever may write this, plus
whoever wrote it" without a clause of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, UnicodeText

from abilian.core.entities import Entity
from abilian.core.models import comment as comment_module
from abilian.core.models.comment import Comment
from abilian.core.models.subjects import User
from abilian.services import security_service
from abilian.services.security import ADMIN
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


@comment_module.register
class CommentableThing(Entity):
    """The only commentable model in the codebase, and it is a fixture."""

    __tablename__ = "test_commentable_thing"

    note = Column(UnicodeText, default="")


def _user(db: SQLAlchemy, email: str) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    return user


def _thing_with_comment(db: SQLAlchemy, author: User):
    thing = CommentableThing(name="A thing")
    db.session.add(thing)
    db.session.flush()

    comment = Comment(body="a remark", entity=thing)
    comment.owner = comment.creator = author
    db.session.add(comment)
    db.session.commit()
    return thing, comment


# --- the rule, asked of the engine -------------------------------------------


def test_the_author_may_edit_and_delete_their_own(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    """This is what `roles=OWNER` buys: no clause comparing owners by hand."""
    ensure_services_started(["security"])
    author = _user(db, "author@example.com")
    _thing, comment = _thing_with_comment(db, author)
    db.session.commit()

    with client_login(client, author), app.test_request_context("/"):
        from flask import g

        g.user = author
        comments = app.extensions["comments"]
        assert comments.can_write(comment)
        assert comments.can_delete(comment)


def test_somebody_else_may_not(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    ensure_services_started(["security"])
    author = _user(db, "author@example.com")
    stranger = _user(db, "stranger@example.com")
    _thing, comment = _thing_with_comment(db, author)
    db.session.commit()

    with client_login(client, stranger), app.test_request_context("/"):
        from flask import g

        g.user = stranger
        comments = app.extensions["comments"]
        assert not comments.can_write(comment)
        assert not comments.can_delete(comment)


def test_a_site_admin_may(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    """ADMIN is in every permission's role set, so this needs no clause either."""
    ensure_services_started(["security"])
    author = _user(db, "author@example.com")
    admin = _user(db, "admin@example.com")
    security_service.grant_role(admin, ADMIN)
    _thing, comment = _thing_with_comment(db, author)
    db.session.commit()

    with client_login(client, admin), app.test_request_context("/"):
        from flask import g

        g.user = admin
        comments = app.extensions["comments"]
        assert comments.can_write(comment)
        assert comments.can_delete(comment)


# --- and the routes enforce it -----------------------------------------------


def test_a_stranger_cannot_edit_a_comment_through_the_route(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    ensure_services_started(["security"])
    author = _user(db, "author@example.com")
    stranger = _user(db, "stranger@example.com")
    thing, comment = _thing_with_comment(db, author)
    db.session.commit()

    with client_login(client, stranger):
        response = client.get(f"/comments/{thing.id}/{comment.id}/edit")

    assert response.status_code == 403


def test_a_stranger_cannot_delete_a_comment_through_the_route(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    ensure_services_started(["security"])
    author = _user(db, "author@example.com")
    stranger = _user(db, "stranger@example.com")
    thing, comment = _thing_with_comment(db, author)
    db.session.commit()

    with client_login(client, stranger):
        response = client.get(f"/comments/{thing.id}/{comment.id}/delete")

    assert response.status_code == 403


def test_the_author_can_open_the_edit_form(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    """The fix must not take the feature from the people it is for."""
    ensure_services_started(["security"])
    author = _user(db, "author@example.com")
    thing, comment = _thing_with_comment(db, author)
    db.session.commit()

    with client_login(client, author):
        response = client.get(f"/comments/{thing.id}/{comment.id}/edit")

    assert response.status_code == 200
