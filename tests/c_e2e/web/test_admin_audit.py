# Copyright (c) 2026, Abilian SAS

"""The log of changes says who did what, to which object, and what changed."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING

from flask import url_for
from flask_login import login_user

from abilian.services import audit_service
from tests.util import client_login

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def test_a_line_says_who_changed_what_and_how(
    app: Flask,
    client: FlaskClient,
    admin_user: User,
    community1: Community,
    db: SQLAlchemy,
) -> None:
    """The log starts after the community is made: the rename is a change of its own."""
    if audit_service.running:
        audit_service.stop()
    old = community1.name
    db.session.commit()
    # The changes made while nobody logged them stay on the object: forget them.
    vars(community1).pop("__changes__", None)
    audit_service.start()
    with app.test_request_context():
        login_user(admin_user)
        community1.name = "The Renamed"
        db.session.commit()

    with client_login(client, admin_user):
        html = unescape(client.get(url_for("admin.audit")).get_data(as_text=True))

    assert f"{admin_user.name}</strong></a> changed the community" in html
    assert f"<del>{old}</del> → <ins>The Renamed</ins>" in html
