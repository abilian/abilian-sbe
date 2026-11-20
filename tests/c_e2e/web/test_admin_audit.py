# Copyright (c) 2026, Abilian SAS

"""The log of changes says who did what, to which object, and what changed."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from html import unescape
from typing import TYPE_CHECKING

import pytz
from babel.dates import LOCALTZ
from flask import url_for
from flask_login import login_user

from abilian.services import audit_service
from abilian.services.audit import UPDATE, AuditEntry
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


def test_the_logs_address_takes_a_whole_second_and_refuses_nonsense(
    client: FlaskClient, admin_user: User
) -> None:
    with client_login(client, admin_user):
        whole = client.get(url_for("admin.audit", before="2026-11-19T10:00:00"))
        newer = client.get(url_for("admin.audit", after="2026-11-19T10:00:00"))
        day = client.get(url_for("admin.audit", before="tomorrow"))
        person = client.get(url_for("admin.audit", user="abc"))

    assert (whole.status_code, newer.status_code) == (200, 200)
    assert (day.status_code, person.status_code) == (400, 400)
    # Filtering again from a page of newer changes starts afresh.
    assert 'name="after"' not in newer.get_data(as_text=True)


def test_a_change_with_no_actor_is_the_systems(
    client: FlaskClient, admin_user: User, community1: Community, db: SQLAlchemy
) -> None:
    """Done outside a request (a migration, the CLI), it was made by nobody."""
    db.session.add(
        AuditEntry(
            type=UPDATE,
            entity_id=community1.id,
            entity_type=community1.entity_type,
            entity_name=community1.name,
        )
    )
    db.session.commit()

    with client_login(client, admin_user):
        response = client.get(url_for("admin.audit"))

    assert response.status_code == 200
    assert "<em>The system</em>" in response.get_data(as_text=True)


def _at_local(day: date, hour: int, minute: int) -> datetime:
    """A moment of the site's time zone, as the log stores it (UTC, naive)."""
    local = LOCALTZ.localize(datetime(day.year, day.month, day.day, hour, minute))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


def test_a_day_shows_the_log_up_to_its_end_in_the_sites_time_zone(
    client: FlaskClient, admin_user: User, community1: Community, db: SQLAlchemy
) -> None:
    """Whatever the browser's time zone: it sends the day, not a moment."""
    day, next_day = date(2026, 3, 9), date(2026, 3, 10)
    for moment in (_at_local(day, 23, 30), _at_local(next_day, 0, 30)):
        db.session.add(
            AuditEntry(
                type=UPDATE,
                happened_at=moment,
                entity_id=community1.id,
                entity_type=community1.entity_type,
                entity_name=community1.name,
            )
        )
    db.session.commit()

    with client_login(client, admin_user):
        page = client.get(url_for("admin.audit", day=day.isoformat()))
        nonsense = client.get(url_for("admin.audit", day="tomorrow"))

    html = page.get_data(as_text=True)
    assert f'<time datetime="{day.isoformat()}">' in html
    assert f'<time datetime="{next_day.isoformat()}">' not in html
    assert nonsense.status_code == 400
