# Copyright (c) 2012-2024, Abilian SAS

"""`/health`: whether the app is up and reaches its database.

A platform checks it on the app's own port: it answers without signing in, on a
private site too, and over plain HTTP, which every other page sends to HTTPS.
"""

from __future__ import annotations

import sqlalchemy as sa
from flask import Blueprint, Response

from abilian.core.extensions import db

blueprint = Blueprint("health", __name__)


@blueprint.route("/health")
def health() -> Response:
    """Answer "OK" once the database has answered."""
    db.session.execute(sa.text("SELECT 1"))
    return Response("OK", mimetype="text/plain")


#: Read by Talisman, which otherwise sends a plain-HTTP request to HTTPS.
health.talisman_view_options = {"force_https": False}
