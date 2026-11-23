# Copyright (c) 2026, Abilian SAS

"""Where an app keeps its files: FLASK_INSTANCE_PATH, read from where it starts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.sbe.app import create_app
from abilian.testing.conftest import TestConfig

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_a_relative_instance_path_is_read_from_where_the_app_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flask refuses a relative instance path: the app did not start."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLASK_INSTANCE_PATH", "instance")

    app = create_app(config=TestConfig)

    assert app.instance_path == str((tmp_path / "instance").resolve())
    assert (tmp_path / "instance").is_dir()


def test_an_instance_path_given_to_the_app_wins_over_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FLASK_INSTANCE_PATH", str(tmp_path / "from-env"))

    app = create_app(config=TestConfig, instance_path=str(tmp_path / "given"))

    assert app.instance_path == str(tmp_path / "given")
