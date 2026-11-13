# Copyright (c) 2012-2024, Abilian SAS

"""Elements to build test cases for an :class:`abilian.app.Application`"""

from __future__ import annotations

import contextlib
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING

from flask_login import login_user, logout_user
from hyperlink import URL
from sqlalchemy.exc import DatabaseError

from abilian.services import get_service
from abilian.web import url_for

#: Fixture files shared by more than one test tier.
DATA_DIR = Path(__file__).parent / "data"

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy

__all__ = (
    "class_fqn",
    "cleanup_db",
    "client_login",
    "ensure_services_started",
    "login",
    "path_from_url",
    "stop_all_services",
)


def path_from_url(url) -> str:
    url = str(url)
    return f"/{'/'.join(URL.from_text(url).path)}"


def client_login(client: FlaskClient, user: User) -> AbstractContextManager:
    data = {"email": user.email, "password": user._password}
    response = client.post(url_for("login.login_post"), data=data)
    assert response.status_code == 302
    # assert current_user.is_authenticated
    # assert current_user.id == user.id

    class LoginContext:
        def __enter__(self):
            return None

        def __exit__(self, type, value, traceback):
            response = client.post(url_for("login.logout"))
            assert response.status_code == 302
            # assert current_user.is_anonymous

    return LoginContext()


def login(user, remember=False, force=False):
    """Perform user login for `user`, so that code needing a logged-in user can
    work.

    This method can also be used as a context manager, so that logout is
    performed automatically::

        with login(user):
            assert ...

    .. seealso:: :meth:`logout`
    """
    # self._login_tests_sanity_check()
    success = login_user(user, remember=remember, force=force)
    if not success:
        msg = "User is not active, cannot login; or use force=True"
        raise ValueError(msg)

    class LoginContext:
        def __enter__(self):
            return None

        def __exit__(self, type, value, traceback):
            logout_user()

    return LoginContext()


def cleanup_db(db: SQLAlchemy) -> None:
    """Drop all the tables, in a way that doesn't raise integrity errors."""

    # Need to run this sequence twice for some reason
    _delete_tables(db)
    _delete_tables(db)
    # One more time, just in case ?
    db.drop_all()


def _delete_tables(db: SQLAlchemy) -> None:
    for table in reversed(db.metadata.sorted_tables):
        with contextlib.suppress(DatabaseError):
            db.session.execute(table.delete())


def ensure_services_started(services: list[str]) -> None:
    for service_name in services:
        service = get_service(service_name)
        if not service.running:
            service.start()


def stop_all_services(app: Application) -> None:
    for service in app.service_manager.list_services():
        if service.running:
            service.stop()


def class_fqn(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"
