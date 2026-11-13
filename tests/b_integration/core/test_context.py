# Copyright (c) 2012-2024, Abilian SAS

"""The seam: who is acting, asked once instead of read ambiently everywhere.

The regression these guard against is subtle enough to be worth naming. An
earlier version of `get_current_principal` fell back to flask-login's `current_user`
proxy when `g.user` was absent. Resolving that proxy makes flask-login load a
user *and cache the result* in `g._login_user`; `g` lives on the app context, so
resolving it while no real request is in flight caches an anonymous user that
the next request then inherits instead of loading from the session.

The test harness pushes a request context, so `has_request_context()` is no
guard against this. That version logged every test user out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g

from abilian.core.context import get_current_principal

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy


def test_nobody_acting_is_none_not_an_error(app: Application) -> None:
    """A task, a CLI command and a migration all run with no user."""
    with app.app_context():
        assert get_current_principal() is None


def test_outside_an_app_context_too(app: Application) -> None:
    assert get_current_principal() is None


def test_the_acting_user_when_there_is_one(app: Application, user: User) -> None:
    with app.test_request_context("/"):
        g.user = user
        assert get_current_principal() is user


def test_asking_does_not_log_the_next_request_out(
    client: FlaskClient, user: User, db: SQLAlchemy
) -> None:
    """Asking who is acting must not disturb who is acting.

    Reading the principal before a request -- which `OwnedMixin.__init__` and
    the security service both do, from fixtures and tasks -- used to poison
    flask-login's per-app-context cache, so the request that followed arrived
    anonymous.
    """
    with client.session_transaction() as session:
        session["_user_id"] = user.id

    # The call that used to do the damage.
    assert get_current_principal() is None

    @client.application.route("/__whoami")
    def whoami() -> str:
        return "anonymous" if get_current_principal() is None else "authenticated"

    assert client.get("/__whoami").data == b"authenticated"
