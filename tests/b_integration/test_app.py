# Copyright (c) 2012-2024, Abilian SAS

"""Application setup: refusing an unsafe config, static routes' roles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from abilian.app import create_app
from abilian.services.security import ADMIN
from abilian.testing.conftest import TestConfig

if TYPE_CHECKING:
    from pathlib import Path


class ProductionWithDefaultKey(TestConfig):
    TESTING = False
    DEBUG = False
    SECRET_KEY = "CHANGEME"  # noqa: S105


def test_the_default_secret_key_stops_a_production_app(tmp_path: Path) -> None:
    """It exited with status 0, so a supervisor saw a clean stop, not a failure."""
    with pytest.raises(SystemExit) as exit_info:
        create_app(config=ProductionWithDefaultKey, instance_path=str(tmp_path))

    assert exit_info.value.code not in (0, None)


def test_a_static_url_with_roles_is_not_public(tmp_path: Path) -> None:
    """The anonymous controller added after the roles' one let everybody in."""
    (tmp_path / "files").mkdir()
    (tmp_path / "files" / "secret.txt").write_text("secret")
    app = create_app(config=TestConfig, instance_path=str(tmp_path / "instance"))
    app.add_static_url(
        "private", str(tmp_path / "files"), endpoint="private_static", roles=[ADMIN]
    )

    response = app.test_client().get("/static/private/secret.txt")

    assert response.status_code != 200
