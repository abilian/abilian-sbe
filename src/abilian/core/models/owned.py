# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, ForeignKey
from whoosh.fields import STORED

from abilian.core.context import get_current_principal

from .base import AUDITABLE, EDITABLE, SEARCHABLE, SYSTEM
from .subjects import User


class OwnedMixin:
    __index_to__ = (
        ("creator", ("creator",)),
        ("creator_name", (("creator_name", STORED),)),
        ("owner", ("owner",)),
        ("owner_name", (("owner_name", STORED),)),
    )

    def __init__(self, *args: list, **kwargs: dict[str, Any]) -> None:
        """Attribute a new entity to whoever is creating it, if anyone is.

        Nobody is, when this runs outside a request: a migration, the CLI, a
        dramatiq task. That used to be spelled as `g.user` inside
        `except (RuntimeError, AttributeError): pass`, which also swallowed any
        real AttributeError raised while assigning.
        """
        user = get_current_principal()
        if user is None:
            return

        if not self.creator:
            self.creator = user
        if not self.owner:
            self.owner = user

    @declared_attr
    def creator_id(cls):
        return Column(ForeignKey(User.id), info=SYSTEM)

    @declared_attr
    def creator(cls):
        primary_join = f"User.id == {cls.__name__}.creator_id"
        return relationship(
            User,
            primaryjoin=primary_join,
            lazy="joined",
            uselist=False,
            info=SYSTEM | SEARCHABLE,
        )

    @property
    def creator_name(self) -> str:
        return str(self.creator) if self.creator else ""

    @declared_attr
    def owner_id(cls):
        return Column(ForeignKey(User.id), info=EDITABLE | AUDITABLE)

    @declared_attr
    def owner(cls):
        primary_join = f"User.id == {cls.__name__}.owner_id"
        return relationship(
            User,
            primaryjoin=primary_join,
            lazy="joined",
            uselist=False,
            info=EDITABLE | AUDITABLE | SEARCHABLE,
        )

    @property
    def owner_name(self) -> str:
        return str(self.owner) if self.owner else ""
