# Copyright (c) 2012-2024, Abilian SAS

"""Objects to schema adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from operator import attrgetter
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from whoosh.fields import ID, TEXT, Schema

from abilian.core.extensions import db

from .schema import accent_folder

if TYPE_CHECKING:
    from sqlalchemy.orm.session import Session

    from abilian.core.entities import Entity
    from abilian.core.models import Model

__all__ = ["SAAdapter", "SchemaAdapter"]


class SchemaAdapter(ABC):
    """Abstract base class for objects to schema adapter.

    The purpose of adapters is that given an object they return kwargs
    for document.
    """

    def __init__(self, model_class, schema) -> None:
        """
        :param:model_class: class of objects instances to be adapted
        :param:schema: :class:`whoosh.fields.Schema` instance
        """

    @staticmethod
    def can_adapt(obj_cls) -> bool:
        """Return True if this class can adapt objects of class `obj_cls`."""
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, pk, **data) -> Any:
        """Returns an object instance given its identifier and optional data
        kwargs.

        :param pk: the primary key to retrieve the object

        :returns: None if not object instance can be returned
        """
        raise NotImplementedError

    @abstractmethod
    def get_document(self, obj) -> dict[str, Any]:
        raise NotImplementedError


class SAAdapter(SchemaAdapter):
    """Adapts an sqlalchemy model.

    A column on the model is indexed if `"searchable"` is set to `True` in
    its `info` field (see :meth:`sqlalchemy.schema.Column.__init__`)

    Additionnaly info can also contains `index_to`. It's expected to be an
    iterable of field names or tuple of (field name, whoosh field
    instance). The default the whoosh field is a
    :class:`whoosh.fields.TEXT` instance.

    When `index_to` is used the column name will *not* be indexed on the same
    field name unless specified in `index_to`.

    If multiple field names are passed to `index_to` the values will be
    concatenated with a space.

    `index_to` is useful for::

    * index many attributes to on field names, for exemple index `title`
    and `description` to a `_full_text` field
    * define new fields on schema
    """

    doc_attrs: dict[str, Any]

    def __init__(self, model_class: type[Model], schema: Schema) -> None:
        """
        :param:model_class: a sqlalchemy model class
        :param:schema: :class:`whoosh.fields.Schema` instance
        """
        assert issubclass(model_class, db.Model)

        self.model_class = model_class
        self.indexable = getattr(model_class, "__indexable__", False)
        self.index_to = self.get_index_to(model_class)
        self.doc_attrs = {}
        if self.indexable:
            self._build_doc_attrs(model_class, schema)

    @staticmethod
    def can_adapt(obj_cls: Any) -> bool:
        return issubclass(obj_cls, db.Model)

    def get_index_to(self, model_class: type[Model]) -> tuple:
        result = []
        classes = model_class.mro()
        for cls in classes:
            if hasattr(cls, "__index_to__"):
                result += cls.__index_to__
        return tuple(result)

    def _build_doc_attrs(self, model_class: type[Model], schema: Schema) -> None:
        mapper = sa.inspect(model_class)

        args = self.doc_attrs
        # Any field not in schema will be stored here.
        # After all field have been discovered, we add the missing ones.
        field_definitions = {}

        def setup_field(
            attr_name: str, field_name: tuple[str, type | ID] | str
        ) -> None:
            field_def = False
            if not isinstance(field_name, str):
                field_name, field_def = field_name

            if field_name not in schema and (
                field_name not in field_definitions
                or field_definitions[field_name] is False
            ):
                field_definitions[field_name] = field_def

            # attrgetter offers dotted name support. Useful for attributes on
            # related objects.
            args.setdefault(field_name, {})[attr_name] = attrgetter(attr_name)

        # model level definitions
        for name, field_names in self.index_to:
            if isinstance(field_names, str):
                field_names = (field_names,)
            for field_name in field_names:
                setup_field(name, field_name)

        # per column definitions; a `column_property` (an SQL expression) is no
        # column of the table, and nothing to index
        for col in mapper.columns:
            if not isinstance(col, sa.Column):
                continue
            name = col.name
            info = col.info

            if not info.get("searchable"):
                continue

            index_to = info.get("index_to", (name,))
            if isinstance(index_to, str):
                index_to = (index_to,)

            for field_name in index_to:
                setup_field(name, field_name)

        # add missing fields to schema
        for field_name, field_def in field_definitions.items():
            if field_name in schema:
                continue

            if field_def is False:
                field_def = TEXT(stored=True, analyzer=accent_folder)

            # logger.debug(
            #     "Adding field to schema:\n  Model: {model}\n"
            #     '  Field: "{field_name}" {field_def}',
            #     model=model_class._object_type(),
            #     field_name=field_name,
            #     field_def=field_def,
            # )
            schema.add(field_name, field_def)

    def retrieve(self, pk: int, _session: Session | None = None, **data: Any) -> Entity:
        if _session is None:
            _session = db.session()
        return _session.query(self.model_class).get(pk)

    def get_document(self, obj: Model) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not self.indexable:
            return result

        # Cache because the same attribute may be needed by many fields, i.e
        # "title" on "title" field and "full_text" field for example.
        cached = {}
        # Negative cache. Might be used especially with dotted names.
        missed = set()

        for field_name, attrs in self.doc_attrs.items():
            values = []

            for a, getter in attrs.items():
                if a in missed:
                    continue

                if a not in cached:
                    try:
                        val = getter(obj)
                    except AttributeError:
                        missed.add(a)
                        continue
                    else:
                        cached[a] = val

                val = cached[a]
                if val is not None:
                    if isinstance(val, (list, tuple)):
                        val = " ".join(val).strip()
                    values.append(val)

            values = [v for v in values if v]

            if values:
                if len(values) == 1:
                    result[field_name] = values[0]
                else:
                    result[field_name] = " ".join(values)

        return result
