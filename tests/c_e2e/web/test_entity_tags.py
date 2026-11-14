# Copyright (c) 2012-2024, Abilian SAS

"""Editing an entity's tags through the tags extension's view."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.sbe.apps.communities.models import Community


def test_the_tag_edit_page_opens(
    client: FlaskClient, login_admin: User, community1: Community, db_session
) -> None:
    """The view sets its form for each entity: it has none of its own."""
    response = client.get(url_for("entity_tags.edit", object_id=community1.id))
    assert response.status_code == 200
