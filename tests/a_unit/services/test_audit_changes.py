# Copyright (c) 2012-2026, Abilian SAS

"""What a change to an object shows a person: the fields they read."""

from __future__ import annotations

from abilian.services.audit.models import Changes


def test_a_change_shows_the_fields_a_person_reads() -> None:
    changes = Changes()
    for name in (
        "name",
        "_entity_type",
        "folder_id",
        "_content_id",
        "content_digest",
        "description",
    ):
        changes.set_column_changes(name, "before", "after")

    assert changes.shown_columns() == ["description", "name"]
