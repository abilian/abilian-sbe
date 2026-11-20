# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from sqlalchemy import Column, Text, UnicodeText

from abilian.core.entities import SEARCHABLE, Entity


class DummyContact(Entity):
    salutation = Column(UnicodeText, default="")
    first_name = Column(UnicodeText, default="", info=SEARCHABLE)
    last_name = Column(UnicodeText, default="", info=SEARCHABLE)
    email = Column(Text, default="")
