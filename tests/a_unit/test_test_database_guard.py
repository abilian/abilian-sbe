# Copyright (c) 2026, Abilian SAS

"""The tests drop every table: they refuse a database not made for them."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from abilian.testing.util import NotATestDatabaseError, check_test_database

TMP = Path(tempfile.gettempdir()).resolve()


@pytest.mark.parametrize(
    "uri",
    [
        "sqlite://",
        "sqlite:///:memory:",
        f"sqlite:///{TMP}/run/sbe.db",
        "sqlite:///sbe_test.db",
        "postgresql://sbe:sbe@postgres/sbe_test",
        "mysql+pymysql://sbe:sbe@127.0.0.1/sbe_test?charset=utf8mb4",
    ],
)
def test_a_test_database_is_accepted(uri: str) -> None:
    check_test_database(uri)


@pytest.mark.parametrize(
    "uri",
    [
        "postgresql://localhost/sbe-demo",
        "postgresql://sbe:secret@db/sbe",
        "sqlite:////srv/sbe/data.db",
        "sqlite:///instance/sbe.db",
    ],
)
def test_another_database_is_refused(uri: str) -> None:
    with pytest.raises(NotATestDatabaseError, match="Refusing to run the tests"):
        check_test_database(uri)


def test_the_refusal_hides_the_password() -> None:
    with pytest.raises(NotATestDatabaseError) as error:
        check_test_database("postgresql://sbe:secret@db/sbe")

    assert "secret" not in str(error.value)
