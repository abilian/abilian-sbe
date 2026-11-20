# Copyright (c) 2012-2024, Abilian SAS

"""Configuration and injectable fixtures for Pytest.

Reuses fixtures defined in abilian-core.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from babel.messages.frontend import CommandLineInterface

from abilian.testing.conftest import *  # noqa: F403

if TYPE_CHECKING:
    import pytest

#: The app's catalogs: git keeps their .po files, not the .mo files the app reads.
CATALOGS = ("src/abilian/translations", "src/abilian/sbe/translations")


def pytest_sessionstart(session: pytest.Session) -> None:
    """Compile the catalogs first, wherever the tests run: without them, the site
    under test speaks no French, and the tests of its French fail."""
    root = Path(__file__).parent.parent
    for catalog in CATALOGS:
        CommandLineInterface().run(
            ["pybabel", "-q", "compile", "-d", str(root / catalog)]
        )
