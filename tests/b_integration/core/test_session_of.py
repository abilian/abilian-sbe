# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy.exc

from abilian.core.models.subjects import User
from abilian.core.sqlalchemy.session import session_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def test_an_object_in_no_session_is_refused() -> None:
    with pytest.raises(sqlalchemy.exc.InvalidRequestError, match="no session"):
        session_of(User(email="nobody@example.com"))


def test_an_added_object_gives_its_session(session: Session) -> None:
    user = User(email="somebody@example.com")
    session.add(user)
    assert session_of(user) is session()
