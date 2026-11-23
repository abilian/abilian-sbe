# Copyright (c) 2026, Abilian SAS

"""A folder's "Everything in it" page names whose each document is.

The owners were looked up with SQL `concat()`, which SQLite only has since 3.44:
on an older one, the page failed.
"""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    import pytest
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def test_everything_in_a_folder_names_the_owner_of_each_document(
    community1: Community,
    client: FlaskClient,
    db: SQLAlchemy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    ensure_services_started(["security", "indexing"])
    manager = community1.test_user
    community1.set_membership(manager, MANAGER)
    author = User(
        email="ada@example.com", first_name="Ada", last_name="Lovelace", can_login=True
    )
    db.session.add(author)
    document = community1.folder.create_document(title="notes.txt")
    document.set_content(b"Notes.", "text/plain")
    document.owner = author
    db.session.commit()
    url = url_for(
        "documents.descendants_view",
        community_id=community1.slug,
        folder_id=community1.folder.id,
    )

    with client_login(client, manager):
        response = client.get(url)

    assert response.status_code == 200
    html = unescape(response.get_data(as_text=True))
    entry = html.split("<span>notes.txt</span>")[1].split("</li>")[0]
    assert "· Ada Lovelace" in entry
