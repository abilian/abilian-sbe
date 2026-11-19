# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from flask import Flask


def init_logging(app: Flask) -> None:
    run_from_cli = app.config.get("RUN_FROM_CLI")

    if run_from_cli and not app.debug:
        print("Running from CLI, skipping logging init (use --debug to enable)")
        logger.configure(handlers=[])
    else:
        init_loguru(app)


class InterceptHandler(logging.Handler):
    def emit(self, record) -> None:
        logger_opt = logger.opt(depth=6, exception=record.exc_info)
        logger_opt.log(record.levelno, record.getMessage())


def init_loguru(app: Flask) -> None:
    """Register loguru as (sole) handler."""
    if app.debug:
        level = "DEBUG"
    else:
        level = "INFO"

    logger.remove()
    # Without `diagnose`, which loguru turns on by default: it prints the value of
    # every variable in a traceback, which puts passwords and tokens in the logs, and
    # runs code to do so. A request's `current_user` is a proxy: printing it loads
    # the user, and a database that fails there logged the error again, which
    # printed it again, and so on, holding a CPU and the request for minutes.
    logger.add(sys.stderr, level=level, diagnose=False)

    app.logger.handlers = [InterceptHandler()]
    logger.info("Loguru initialized")
