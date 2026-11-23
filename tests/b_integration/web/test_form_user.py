# Copyright (c) 2026, Abilian SAS

"""A form that shows its fields by role is given the user it shows them to: it does
not look up whoever is logged in."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from wtforms import StringField

from abilian.services.security import READ, Role
from abilian.web.forms import Form, FormPermissions
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy

EDITOR = Role("tests:editor")


class NotesForm(Form):
    _permissions = FormPermissions(
        read=Role("anonymous"), fields_read={"notes": EDITOR}
    )

    title = StringField()
    notes = StringField()


@pytest.fixture
def security(db: SQLAlchemy) -> None:
    ensure_services_started(["security"])


def test_the_fields_are_those_the_given_user_may_read(
    app: Application, security: None, user: User
) -> None:
    with app.test_request_context():
        form = NotesForm(permission=READ, user=user)

    assert "title" in form
    assert "notes" not in form


def test_a_form_filtered_by_role_wants_its_user(
    app: Application, security: None
) -> None:
    with app.test_request_context(), pytest.raises(TypeError):
        NotesForm(permission=READ)
