# Copyright (c) 2012-2024, Abilian SAS

"""Configuration and injectable fixtures for Pytest.

Reuses fixtures defined in abilian-core.
"""

from __future__ import annotations

from sqlalchemy.util import deprecations

from abilian.testing.conftest import *  # noqa: F403

# Report what SQLAlchemy 2.0 removes; the filters in pyproject.toml make it an
# error, so nothing new comes in before the upgrade.
deprecations.SQLALCHEMY_WARN_20 = True
