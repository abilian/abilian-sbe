# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import runpy

import click
import sqlalchemy as sa
from flask.cli import with_appcontext
from flask_migrate import stamp, upgrade
from flask_super.cli import command

from abilian.core.extensions import db
from abilian.core.models.subjects import User, create_root_user
from abilian.services import get_service
from abilian.services.security import ADMIN


@command()
@with_appcontext
def initdb() -> None:
    """Create the tables, at the schema of the latest migration, and say so."""
    db.create_all()
    # Marked at the latest migration, the database takes the next
    # `flask db upgrade`; left unmarked, it would replay them all.
    stamp()
    create_root_user()


@command()
@with_appcontext
def preparedb() -> None:
    """Make the database ready for this version: created when there is none,
    brought up to date by the migrations when there is one.

    What a deployment runs before each start, the first included.
    """
    if sa.inspect(db.engine).get_table_names():
        upgrade()
    else:
        initdb.callback()


@command()
@click.confirmation_option("-y", "--yes", prompt="Drop every table of the database?")
@with_appcontext
def dropdb() -> None:
    """Drop every table of the database, and all it holds. -y skips asking."""
    db.drop_all()
    click.echo(f"Dropped the tables of {db.engine.url.render_as_string()}")


@command()
@click.argument("path", type=click.Path(exists=True))
@with_appcontext
def script(path) -> None:
    """Run the given script in the app context."""
    runpy.run_path(path, run_name="__main__")


@command()
@click.argument("email")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    envvar="SBE_PASSWORD",
    help="Asked for when not given, or read from SBE_PASSWORD: unlike an "
    "argument, neither shows in the list of processes.",
)
@click.option(
    "--role",
    # The one role given on the whole site; the others are given in a community.
    type=click.Choice([ADMIN.name]),
    help="A role on the whole site.",
)
@click.option("--name", help="The last name.")
@click.option("--first_name", help="The first name.")
@with_appcontext
def createuser(
    email: str,
    password: str,
    role: str | None = None,
    name: str | None = None,
    first_name: str | None = None,
) -> None:
    """Create a user who can sign in with EMAIL."""
    if User.query.filter(User.email == email).count() > 0:
        msg = f"A user with email '{email}' already exists"
        raise click.ClickException(msg)

    user = User(
        email=email,
        password=password,
        last_name=name,
        first_name=first_name,
        can_login=True,
    )
    db.session.add(user)
    if role:
        get_service("security").grant_role(user, role)
    db.session.commit()
    click.echo(f"User {email} added")
