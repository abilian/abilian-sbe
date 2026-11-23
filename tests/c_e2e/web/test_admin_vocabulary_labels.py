# Copyright (c) 2026, Abilian SAS

"""A vocabulary's labels, on the admin page that lists them, are text."""

from __future__ import annotations

from abilian.web import url_for

# Vocabularies are classes, registered once: the vocabulary tests count them all.
from tests.c_e2e.services.test_vocabularies import Voc


def test_a_label_stored_with_a_script_is_shown_as_text(
    client, login_admin, session
) -> None:
    # Stored as is, as an import or another client would: not through the form,
    # which keeps a few tags only.
    session.add(Voc(label="<script>alert(1)</script>Urgent", position=0))
    session.commit()

    html = client.get(url_for("admin.vocabularies")).get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "alert(1)Urgent" in html
