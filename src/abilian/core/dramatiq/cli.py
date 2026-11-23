# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from pathlib import Path

import click
from filelock import FileLock, Timeout
from flask import current_app
from flask.cli import with_appcontext

from .scheduler import run_scheduler

#: In the instance folder: one scheduler per site, wherever it is started from.
SCHEDULER_LOCK_FILE = "scheduler.lock"


@click.command()
@with_appcontext
def scheduler() -> None:
    """Queue the periodic tasks (digests, upload cleanup, Maildir) on schedule.

    Runs until stopped. One per site: a second one would queue every task
    twice, so it exits with an error while another runs.
    """
    lock = FileLock(Path(current_app.instance_path) / SCHEDULER_LOCK_FILE)
    try:
        lock.acquire(blocking=False)
    except Timeout:
        msg = f"A scheduler is running already (it holds {lock.lock_file})"
        raise click.ClickException(msg) from None
    try:
        run_scheduler(dict(current_app.config))
    finally:
        lock.release()
