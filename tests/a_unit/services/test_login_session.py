# Copyright (c) 2012-2026, Abilian SAS

"""When a sign-in ended, as the administration's sign-ins page shows it."""

from __future__ import annotations

from datetime import datetime, timedelta

from abilian.services.auth.models import IDLE_LIMIT, LoginSession


def _session(idle: timedelta, ended_at: datetime | None = None) -> LoginSession:
    now = datetime.utcnow()
    return LoginSession(
        started_at=now - idle - timedelta(hours=2),
        last_active_at=now - idle,
        ended_at=ended_at,
    )


def test_a_recent_sign_in_is_still_on() -> None:
    assert _session(idle=timedelta(minutes=5)).end is None


def test_a_sign_in_left_idle_ended_at_its_last_request() -> None:
    session = _session(idle=IDLE_LIMIT + timedelta(minutes=1))

    assert session.end == session.last_active_at


def test_a_sign_out_ends_a_sign_in() -> None:
    signed_out = datetime(2026, 11, 19, 9, 0)

    assert _session(idle=timedelta(0), ended_at=signed_out).end == signed_out
