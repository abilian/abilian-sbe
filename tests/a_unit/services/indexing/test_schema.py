# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from flask_login import AnonymousUserMixin

from abilian.services.indexing.schema import indexable_role
from abilian.services.security.models import ANONYMOUS, READER


def test_indexable_role() -> None:
    assert indexable_role(ANONYMOUS) == "role:anonymous"
    assert indexable_role(AnonymousUserMixin()) == "role:anonymous"
    assert indexable_role(READER) == "role:reader"
