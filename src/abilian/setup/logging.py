# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import inspect
import logging
import sys
from typing import TYPE_CHECKING

from flask.logging import default_handler
from loguru import logger

if TYPE_CHECKING:
    from flask import Flask


def init_logging(app: Flask) -> None:
    """Log through loguru, in every process: the web app, and the `flask`
    commands, the worker and the scheduler first, whose logs are as needed.

    The standard `logging` module, which Dramatiq and APScheduler use, goes
    through loguru too, so that one process writes in one format.

    Safe to call again, as each `create_app` does: it replaces loguru's sinks
    and the root logger's handlers instead of adding to them. Replacing is
    deliberate, as any handler left on the root logger would print each
    record a second time. That includes handlers others put there, pytest's
    log capture among them.
    """
    level = "DEBUG" if app.debug else "INFO"

    logger.remove()
    # Without `diagnose`, which loguru turns on by default: it prints the value of
    # every variable in a traceback, which puts passwords and tokens in the logs, and
    # runs code to do so. A request's `current_user` is a proxy: printing it loads
    # the user, and a database that fails there logged the error again, which
    # printed it again, and so on, holding a CPU and the request for minutes.
    logger.add(sys.stderr, level=level, diagnose=False)

    # Every record of the standard module, through its root logger: Flask's own
    # handler leaves, or the app's records would come out twice.
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    app.logger.removeHandler(default_handler)


class InterceptHandler(logging.Handler):
    """Hand a record of the standard `logging` module over to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # The frame that called the standard logger: past this one, then past
        # the module's own.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.patch(lambda r: r.update(name=record.name)).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())
