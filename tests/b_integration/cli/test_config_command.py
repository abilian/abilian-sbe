# Copyright (c) 2012-2024, Abilian SAS

"""`flask config` shows the settings, not their secrets nor the environment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.cli.dev import config

if TYPE_CHECKING:
    import pytest

    from abilian.app import Application


def test_secrets_are_masked(app: Application, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(app.config, "SECRET_KEY", "the-secret-key")
    monkeypatch.setitem(app.config, "SENTRY_DSN", "https://abc123@sentry.example.org/1")
    monkeypatch.setitem(app.config, "MAIL_PASSWORD", "the-mail-password")
    monkeypatch.setitem(
        app.config, "REDIS_URI", "redis://default:the-redis-password@redis:6379/0"
    )
    monkeypatch.setenv("SOME_SHELL_TOKEN", "the-shell-token")

    result = app.test_cli_runner().invoke(config)

    assert result.exit_code == 0, result.output
    for secret in ("the-secret-key", "abc123", "the-mail-password"):
        assert secret not in result.output
    assert "the-redis-password" not in result.output
    assert "REDIS_URI: redis://default:********@redis:6379/0" in result.output
    assert "SITE_NAME: Abilian Test" in result.output
    assert "the-shell-token" not in result.output
