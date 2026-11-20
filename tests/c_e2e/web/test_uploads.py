# Copyright (c) 2012-2024, Abilian SAS

"""The upload endpoint behind attachments and photos in forms."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from flask import url_for

from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User


def test_an_uploaded_file_can_be_read_back_by_its_handle(
    client: FlaskClient, user: User, db_session
) -> None:
    with client_login(client, user):
        response = client.post(
            url_for("uploads.new_file"),
            data={"file": (BytesIO(b"some content"), "notes.txt", "text/plain")},
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200
        stored = client.get(response.json["url"])

    assert stored.status_code == 200
    assert stored.data == b"some content"
