# Copyright (c) 2026, Abilian SAS

"""The log of changes says who did what, to which object, and what changed."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from html import unescape
from typing import TYPE_CHECKING

from flask import url_for
from flask_login import login_user

from abilian.services import audit_service
from abilian.services.audit import AuditEntry
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


def _renamed(
    app: Flask, admin_user: User, community: Community, db: SQLAlchemy, name: str
) -> None:
    """`admin_user` renames `community`, with the audit service logging it."""
    if audit_service.running:
        audit_service.stop()
    db.session.commit()
    vars(community).pop("__changes__", None)
    audit_service.start()
    with app.test_request_context():
        login_user(admin_user)
        community.name = name
        db.session.commit()


def test_a_period_leaves_out_what_came_before_it(
    app: Flask,
    client: FlaskClient,
    admin_user: User,
    community1: Community,
    db: SQLAlchemy,
) -> None:
    _renamed(app, admin_user, community1, db, "=Long ago")
    entry = AuditEntry.query.filter(AuditEntry.entity_id == community1.id).one()
    entry.happened_at = datetime.utcnow() - timedelta(days=60)
    db.session.commit()

    with client_login(client, admin_user):
        everything = unescape(client.get(url_for("admin.audit")).get_data(as_text=True))
        month = unescape(
            client.get(url_for("admin.audit", period="month")).get_data(as_text=True)
        )
        unknown = client.get(url_for("admin.audit", period="nonsense"))

    assert "<ins>=Long ago</ins>" in everything
    assert "<ins>=Long ago</ins>" not in month
    assert '<option value="month" selected>' in month
    assert unknown.status_code == 400


def test_the_log_goes_to_a_spreadsheet_as_filtered(
    app: Flask,
    client: FlaskClient,
    admin_user: User,
    community1: Community,
    db: SQLAlchemy,
) -> None:
    _renamed(app, admin_user, community1, db, "=Renamed")

    with client_login(client, admin_user):
        page = client.get(url_for("admin.audit", period="week")).get_data(as_text=True)
        response = client.get(url_for("admin.audit_export", period="week"))

    assert url_for("admin.audit_export", period="week") in unescape(page)
    assert response.mimetype == "text/csv"
    lines = list(csv.reader(io.StringIO(response.get_data(as_text=True).lstrip("﻿"))))
    assert lines[0] == [
        "Date",
        "Person",
        "E-mail",
        "Action",
        "Kind",
        "Object",
        "Detail",
    ]
    renamed = next(line for line in lines if line[5] == "'=Renamed")
    assert renamed[1:5] == [admin_user.name, admin_user.email, "changed", "Community"]
    assert "name" in renamed[6].split(", ")
