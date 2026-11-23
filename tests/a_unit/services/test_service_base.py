# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import pytest

from abilian.services import Service


def test_a_service_needs_a_name() -> None:
    """The default name is "", which the check for None let through."""

    class Nameless(Service):
        pass

    with pytest.raises(ValueError, match="Service must have a name"):
        Nameless()
