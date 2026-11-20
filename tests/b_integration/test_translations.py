# Copyright (c) 2026, Abilian SAS

"""The French interface reads every catalog: Core's under SBE's."""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.i18n import _, force_locale

if TYPE_CHECKING:
    from flask import Flask


def test_core_strings_reach_the_french_interface(app: Flask) -> None:
    """A near-empty `fr_FR` catalog in Core once won over `fr` for French, so
    Core's strings, such as Mon fil's "All" filter, stayed in English."""
    with app.test_request_context("/"), force_locale("fr"):
        assert str(_("All")) == "Tous"
        assert str(_("My feed")) == "Mon fil"
