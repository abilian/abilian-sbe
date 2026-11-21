# Copyright (c) 2012-2024, Abilian SAS

"""Every process logs, and in one format: loguru's.

The worker and the scheduler are `flask` commands; they log like the web app,
and so do the libraries that use the standard `logging` module, Dramatiq first.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from loguru import logger

from abilian.sbe.app import create_app
from abilian.testing.conftest import TestConfig

if TYPE_CHECKING:
    import pytest


class CommandConfig(TestConfig):
    """A `flask` command in production, `flask worker` say."""

    #: What Flask sets for every `flask` command.
    RUN_FROM_CLI = True
    DEBUG = False


def test_a_flask_command_logs(capfd: pytest.CaptureFixture[str]) -> None:
    create_app(config=CommandConfig)

    logger.error("a task failed")

    assert "a task failed" in capfd.readouterr().err


def test_the_standard_logging_goes_through_loguru() -> None:
    create_app(config=CommandConfig)
    messages: list[str] = []
    sink = logger.add(messages.append, format="{level} {name} {function} {message}")
    try:
        logging.getLogger("dramatiq.worker.WorkerThread").error("boom")
    finally:
        logger.remove(sink)

    # Where it was logged from, here: not from inside the `logging` module.
    where = "dramatiq.worker.WorkerThread test_the_standard_logging_goes_through_loguru"
    assert messages == [f"ERROR {where} boom\n"]
