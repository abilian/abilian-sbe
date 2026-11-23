# Copyright (c) 2026, Abilian SAS

"""Logging an error shows where it happened, not the values of its variables."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

from loguru import logger

from abilian.setup.logging import init_logging

if TYPE_CHECKING:
    import pytest


class Probe:
    """A value whose printing is seen: as `current_user` is, a proxy that loads."""

    printed = 0

    def __repr__(self) -> str:
        Probe.printed += 1
        return "probe"


def _fails(value: Probe) -> None:
    raise ValueError(value)


def test_logging_an_error_runs_nothing_of_what_was_in_its_frames() -> None:
    init_logging(SimpleNamespace(debug=True, logger=logging.getLogger("probe")))
    Probe.printed = 0
    try:
        _fails(Probe())
    except ValueError:
        logger.exception("It failed.")

    # Once, for the exception's own message; not again for each frame's variables.
    assert Probe.printed == 1


def test_init_logging_twice_logs_each_record_once(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """`create_app` runs it for each app: handlers must not pile up."""
    app = SimpleNamespace(debug=False, logger=logging.getLogger("twice"))
    init_logging(app)
    init_logging(app)

    logging.getLogger("twice").error("only once")

    assert capfd.readouterr().err.count("only once") == 1
    root_handlers = logging.getLogger().handlers
    assert [type(h).__name__ for h in root_handlers] == ["InterceptHandler"]
