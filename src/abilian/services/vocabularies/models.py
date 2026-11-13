# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
import sqlalchemy.event
import sqlalchemy.orm
from flask_sqlalchemy.query import Query
from sqlalchemy import Column

from abilian.core.extensions import db
from abilian.core.util import slugify

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

_BaseMeta = db.Model.__class__


class VocabularyQuery(Query):
    def active(self) -> VocabularyQuery:
        """Returns only valid vocabulary items."""
        return self.filter_by(active=True)

    def by_label(self, label):
        """Like `.get()`, but by label."""
        # don't use .first(), so that MultipleResultsFound can be raised
        try:
            return self.filter_by(label=label).one()
        except sa.orm.exc.NoResultFound:
            return None

    def by_position(self, position: int):
        """Like `.get()`, but by position number."""
        # don't use .first(), so that MultipleResultsFound can be raised
        try:
            return self.filter_by(position=position).one()
        except sa.orm.exc.NoResultFound:
            return None


class _VocabularyMeta(_BaseMeta):
    """Metaclass for vocabularies.

    Enforces `__tablename__`.
    """

    def __new__(
        cls: type[_VocabularyMeta],
        name: str,
        bases: tuple[type[Model], ...],
        d: dict[str, Any],
    ) -> type[BaseVocabulary]:
        meta = d.get("Meta")
        group = slugify(meta.group or "", "_")
        if group:
            table_prefix = f"vocabulary_{group}_"
        else:
            table_prefix = "vocabulary_"

        if not hasattr(meta, "name"):
            meta_name = name.lower().replace("vocabulary", "")
            meta.name = meta_name

        d["__tablename__"] = table_prefix + meta.name
        return _BaseMeta.__new__(cls, name, bases, d)


class BaseVocabulary(db.Model, metaclass=_VocabularyMeta):
    """Base abstract class for vocabularies."""

    __abstract__ = True
    query_class = VocabularyQuery

    id = Column(sa.Integer(), primary_key=True, autoincrement=True, nullable=False)
    label = Column(sa.Unicode(255), nullable=False, unique=True)
    active = Column(
        sa.Boolean(), nullable=False, server_default=sa.sql.true(), default=True
    )
    default = Column(
        sa.Boolean(), nullable=False, server_default=sa.sql.false(), default=False
    )
    position = Column(sa.Integer, nullable=False, unique=True)

    __table_args__ = (sa.CheckConstraint(sa.sql.func.trim(sa.sql.text("label")) != ""),)

    # @sa.ext.declarative.declared_attr
    # def __mapper_args__(cls):
    #     return {"order_by": [cls.__table__.c.position.asc()]}

    class Meta:
        label = None
        group = None

    def __str__(self) -> str:
        return self.label

    def __repr__(self) -> str:
        tpl = (
            "<{module}.{cls} id={id} label={label} position={position} "
            "active={active} default={default}>"
        )
        cls = self.__class__
        return tpl.format(
            module=cls.__module__,
            cls=cls.__name__,
            id=self.id,
            label=repr(self.label),
            position=repr(self.position),
            active=repr(self.active),
            default=repr(self.default),
        )


@sa.event.listens_for(BaseVocabulary, "before_insert", propagate=True)
@sa.event.listens_for(BaseVocabulary, "before_update", propagate=True)
def strip_label(mapper, connection, target) -> None:
    """Strip labels at ORM level so the unique=True means something."""
    if target.label is not None:
        target.label = target.label.strip()


@sa.event.listens_for(BaseVocabulary, "before_insert", propagate=True)
def _before_insert(mapper, connection, target) -> None:
    """Set item to last position if position not defined."""
    if target.position is None:
        func = sa.sql.func
        stmt = sa.select(
            [func.coalesce(func.max(mapper.persist_selectable.c.position), -1)]
        )
        target.position = connection.execute(stmt).scalar() + 1


# this is used to hold a reference to Vocabularies generated from
# :func:`Vocabulary`. We use BaseVocabulary.registry._class_registry to find
# existing vocabulary, but it's a WeakValueDictionary. When using model
# generators and reloader the weak ref may be lost, leading to errors such as::
#
# InvalidRequestError: Table 'vocabulary_xxxx' is already defined for this
# MetaData instance.  Specify 'extend_existing=True' to redefine options and
# columns on an existing Table object.
_generated_vocabularies = []


def Vocabulary(name, label=None, group=None):
    assert isinstance(name, str)

    cls_name = f"Vocabulary{name.capitalize()}"
    _name, _label, _group = name.lower(), label, group

    class Meta:
        name = _name
        label = _label
        group = _group

    cls = type(cls_name, (BaseVocabulary,), {"Meta": Meta})
    _generated_vocabularies.append(cls)
    return cls
