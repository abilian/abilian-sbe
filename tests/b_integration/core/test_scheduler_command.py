# Copyright (c) 2012-2024, Abilian SAS

"""`flask scheduler` runs once per site: a second one would queue every task
twice."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock

from abilian.core.dramatiq import cli
from abilian.core.dramatiq.cli import SCHEDULER_LOCK_FILE, scheduler

if TYPE_CHECKING:
    import pytest

    from abilian.app import Application


class SchedulerStub:
    """Stands for `run_scheduler`, which runs until interrupted."""

    def __init__(self) -> None:
        self.runs = 0

    def __call__(self, config: dict) -> int:
        self.runs += 1
        return 0


def test_a_second_scheduler_exits_with_an_error(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = SchedulerStub()
    monkeypatch.setattr(cli, "run_scheduler", run)

    with FileLock(Path(app.instance_path) / SCHEDULER_LOCK_FILE):
        result = app.test_cli_runner().invoke(scheduler)

    assert result.exit_code == 1
    assert "running already" in result.output
    assert run.runs == 0


def test_the_scheduler_runs_and_lets_the_next_one_run(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = SchedulerStub()
    monkeypatch.setattr(cli, "run_scheduler", run)
    runner = app.test_cli_runner()

    results = [runner.invoke(scheduler), runner.invoke(scheduler)]

    assert [r.exit_code for r in results] == [0, 0]
    assert run.runs == 2
