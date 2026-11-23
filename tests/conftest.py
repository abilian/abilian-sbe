# Copyright (c) 2012-2024, Abilian SAS

"""Configuration and injectable fixtures for Pytest.

Reuses fixtures defined in abilian-core.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from babel.messages.frontend import CommandLineInterface
from loguru import logger

from abilian.setup.logging import InterceptHandler
from abilian.testing.conftest import *  # noqa: F403
from abilian.testing.conftest import TestConfig
from abilian.testing.util import NotATestDatabaseError, check_test_database

if TYPE_CHECKING:
    from collections.abc import Iterator

#: The app's catalogs: git keeps their .po files, not the .mo files the app reads.
CATALOGS = ("src/abilian/translations", "src/abilian/sbe/translations")


def pytest_sessionstart(session: pytest.Session) -> None:
    """Check the database is one to wipe out, then compile the catalogs.

    Without the catalogs, wherever the tests run, the site under test speaks no
    French, and the tests of its French fail.
    """
    try:
        check_test_database(TestConfig.SQLALCHEMY_DATABASE_URI)
    except NotATestDatabaseError as e:
        raise pytest.UsageError(str(e)) from e

    root = Path(__file__).parent.parent
    for catalog in CATALOGS:
        CommandLineInterface().run(
            ["pybabel", "-q", "compile", "-d", str(root / catalog)]
        )


#: The root logger as the tests found it, before any app set it up.
ROOT_LOGGING = (tuple(logging.getLogger().handlers), logging.getLogger().level)


@pytest.fixture(autouse=True)
def reset_logging() -> Iterator[None]:
    """Start and end every test with the logging the session started with.

    `create_app` replaces loguru's sinks and the root logger's handlers: an app
    made by one test would otherwise decide where the next ones log.
    """
    _reset_logging()
    yield
    _reset_logging()


def _write_to_stderr(message: str) -> None:
    # `sys.stderr` looked up at each write, not once: pytest swaps it to capture
    # the output, and a test reads what it captured.
    sys.stderr.write(message)


def _reset_logging() -> None:
    logger.remove()
    logger.add(_write_to_stderr, diagnose=False)

    # Only the app's handler goes: pytest adds its own for each test, and
    # removes them itself.
    root = logging.getLogger()
    handlers, level = ROOT_LOGGING
    for handler in root.handlers[:]:
        if isinstance(handler, InterceptHandler):
            root.removeHandler(handler)
    for handler in handlers:
        if handler not in root.handlers:
            root.addHandler(handler)
    root.setLevel(level)
