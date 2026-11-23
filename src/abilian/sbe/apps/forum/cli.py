# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import email
from typing import TextIO

import click
from flask.cli import with_appcontext

from .tasks import check_maildir, process_email


@click.command()
@click.argument("file", type=click.File("r"), default="-")
@with_appcontext
def inject_email(file: TextIO) -> None:
    """Queue the reply email in FILE (stdin by default) to be posted."""
    do_inject_email(file.read())


def do_inject_email(raw: str) -> None:
    """Parse the email `raw` and queue it to be posted, if it is readable."""
    message = email.message_from_string(raw)
    if not raw.strip():
        msg = "No email was given"
        raise click.ClickException(msg)
    if message.defects:
        msg = f"The email has defects: {message.defects}"
        raise click.ClickException(msg)

    # A Dramatiq message is JSON: the email goes as text.
    process_email.send(message.as_string())


@click.command()
@with_appcontext
def check_email() -> None:
    """Post the replies waiting in the current user's Maildir."""
    check_maildir()
