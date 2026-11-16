# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from werkzeug.exceptions import HTTPException

from abilian.core.extensions.login import authenticated, authenticated_user
from abilian.core.models.subjects import User
from tests.util import login

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _is_sent_to_login(error: HTTPException) -> bool:
    response = error.get_response()
    return response.status_code == 302 and "/login" in response.location


def test_an_anonymous_visitor_is_sent_to_login(app: Flask) -> None:
    with app.test_request_context(), pytest.raises(HTTPException) as error:
        authenticated_user()
    assert _is_sent_to_login(error.value)


def test_a_logged_in_user_is_returned(app: Flask, session: Session) -> None:
    user = User(email="logged@example.com", can_login=True)
    session.add(user)
    session.flush()
    with app.test_request_context(), login(user):
        assert authenticated_user() == user


@authenticated
def _view(user: User, item_id: int) -> tuple[User, int]:
    return user, item_id


def test_a_view_gets_the_user_before_its_url_arguments(
    app: Flask, session: Session
) -> None:
    user = User(email="logged@example.com", can_login=True)
    session.add(user)
    session.flush()
    with app.test_request_context(), login(user):
        assert _view(item_id=3) == (user, 3)


def test_a_view_sends_an_anonymous_visitor_to_login(app: Flask) -> None:
    with app.test_request_context(), pytest.raises(HTTPException) as error:
        _view(item_id=3)
    assert _is_sent_to_login(error.value)
