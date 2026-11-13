# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from abilian.app import Application


def test_supported_db(app: Application) -> None:
    # Not really a test, just a check that the test suite is configured
    # with a supported DB
    config = app.config
    sqla_uri = config["SQLALCHEMY_DATABASE_URI"]
    assert re.match(r"(sqlite|postgres(ql)?|mysql|mariadb)(\+\w+)?://.*", sqla_uri)
