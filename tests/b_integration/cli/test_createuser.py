# Copyright (c) 2012-2024, Abilian SAS

"""`flask createuser` and `flask dropdb`: no password in the arguments, and no
silent success."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from abilian.cli.base import createuser, dropdb
from abilian.core.models.subjects import User
from abilian.services import security_service
from abilian.services.security import ADMIN
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy

EMAIL = "ada@example.org"


def created(db: SQLAlchemy) -> User:
    db.session.expire_all()
    return User.query.filter(User.email == EMAIL).one()


def test_the_password_is_asked_for_twice(app: Application, db: SQLAlchemy) -> None:
    result = app.test_cli_runner().invoke(createuser, [EMAIL], input="s3cr3t\ns3cr3t\n")

    assert result.exit_code == 0, result.output
    assert "s3cr3t" not in result.output
    assert created(db).authenticate("s3cr3t")


def test_the_password_is_read_from_the_environment(
    app: Application, db: SQLAlchemy
) -> None:
    result = app.test_cli_runner().invoke(
        createuser, [EMAIL], env={"SBE_PASSWORD": "s3cr3t"}
    )

    assert result.exit_code == 0, result.output
    assert created(db).authenticate("s3cr3t")


def test_an_administrator_is_created_with_the_admin_role(
    app: Application, db: SQLAlchemy
) -> None:
    ensure_services_started(["security"])

    result = app.test_cli_runner().invoke(
        createuser, ["--role", "admin", "--password", "s3cr3t", EMAIL]
    )

    assert result.exit_code == 0, result.output
    assert security_service.has_role(created(db), ADMIN)


def test_a_role_that_cannot_be_given_is_refused(
    app: Application, db: SQLAlchemy
) -> None:
    result = app.test_cli_runner().invoke(
        createuser, ["--role", "manager", "--password", "s3cr3t", EMAIL]
    )

    assert result.exit_code == 2
    assert User.query.filter(User.email == EMAIL).count() == 0


def test_an_existing_email_fails(app: Application, db: SQLAlchemy) -> None:
    runner = app.test_cli_runner()
    runner.invoke(createuser, ["--password", "s3cr3t", EMAIL])

    result = runner.invoke(createuser, ["--password", "other", EMAIL])

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert created(db).authenticate("s3cr3t")


def test_dropdb_asks_first(app: Application, db: SQLAlchemy) -> None:
    db.session.commit()

    result = app.test_cli_runner().invoke(dropdb, input="n\n")

    assert result.exit_code == 1
    assert "user" in sa.inspect(db.engine).get_table_names()
