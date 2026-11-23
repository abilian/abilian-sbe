# Copyright (c) 2012-2024, Abilian SAS

"""audit Service: logs modifications to audited objects.

TODO: In the future, we may decide to:

- Make Models that have the __auditable__ property (set to True) auditable.
- Make Entities that have the __auditable__ property set to False not auditable.
"""

from __future__ import annotations

import contextlib
from inspect import isclass
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy import event, extract
from sqlalchemy.orm import Query, Session
from sqlalchemy.orm.attributes import NEVER_SET, InstrumentedAttribute

from abilian.core.context import get_current_principal
from abilian.core.entities import Entity
from abilian.core.extensions import db
from abilian.services import Service, ServiceState

from .models import CREATION, DELETION, RELATED, UPDATE, AuditEntry, Changes

if TYPE_CHECKING:
    from datetime import datetime

    from flask_sqlalchemy.model import Model
    from sqlalchemy.orm.unitofwork import UOWTransaction

    from abilian.app import Application


class AuditableMeta:
    backref_attr: str | None = None
    audited_attrs: set[InstrumentedAttribute]
    collection_attrs: set[InstrumentedAttribute]
    enduser_ids: list[str]

    def __init__(
        self, name: str | None = None, id_attr: str | None = None, related: bool = False
    ) -> None:
        self.name = name
        self.id_attr = id_attr
        self.related = related
        self.audited_attrs = set()
        self.collection_attrs = set()
        self.enduser_ids = []


class AuditServiceState(ServiceState):
    all_model_classes: set[type]
    model_class_names: dict[str, type]

    # set to True when creating audit entries, to avoid examining a session full
    # of audit entries
    creating_entries = False

    def __init__(self, service: AuditService, *args: Any, **kwargs: Any) -> None:
        super().__init__(service, *args, **kwargs)
        self.all_model_classes = set()
        self.model_class_names = {}


class AuditService(Service):
    name = "audit"
    AppStateClass = AuditServiceState

    _listening = False

    def init_app(self, app: Application) -> None:
        super().init_app(app)

        if not self._listening:
            event.listen(Session, "after_flush", self.create_audit_entries)
            self._listening = True

    def start(self, ignore_state: bool = False) -> None:
        super().start(ignore_state)
        self.register_classes()

    @staticmethod
    def is_auditable(model_or_class: Any) -> bool:
        if hasattr(model_or_class, "__auditable_entity__"):
            return True

        if isclass(model_or_class):
            return issubclass(model_or_class, Entity)
        return isinstance(model_or_class, Entity)

    def register_classes(self) -> None:
        state = self.app_state
        BaseModel = db.Model
        all_models = (
            cls
            for cls in BaseModel.registry._class_registry.values()
            if isclass(cls) and self.is_auditable(cls)
        )
        for cls in all_models:
            self.register_class(cls, app_state=state)

    def register_class(
        self, entity_class: Any, app_state: AuditServiceState | None = None
    ) -> None:
        if not hasattr(entity_class, "__table__"):
            return

        state = app_state if app_state is not None else self.app_state
        if entity_class in state.all_model_classes:
            return

        state.all_model_classes.add(entity_class)
        self.setup_auditable_entity(entity_class)

        assert entity_class.__name__ not in state.model_class_names
        state.model_class_names[entity_class.__name__] = entity_class

        mapper = sa.orm.class_mapper(entity_class)
        # A `column_property` (an SQL expression) is no column of the table: it is
        # computed, never set, and nothing to audit.
        for column in mapper.columns:
            if not isinstance(column, sa.Column):
                continue
            props = mapper.get_property_by_column(column)
            attr = getattr(entity_class, props.key)
            info = column.info

            if info.get("auditable", True):
                entity_class.__auditable__.audited_attrs.add(attr)
                event.listen(attr, "set", self.set_attribute, active_history=True)

        for relation in mapper.relationships:
            if relation.direction is not sa.orm.interfaces.MANYTOMANY:
                continue
            attr = getattr(entity_class, relation.key)
            entity_class.__auditable__.collection_attrs.add(attr)
            event.listen(attr, "append", self.collection_append, active_history=True)
            event.listen(attr, "remove", self.collection_remove, active_history=True)

    def setup_auditable_entity(self, entity_class: Any) -> None:
        meta = AuditableMeta(entity_class.__name__, "id")
        entity_class.__auditable__ = meta

        if not hasattr(entity_class, "__auditable_entity__"):
            return

        related_attr, backref_attr, enduser_ids = entity_class.__auditable_entity__
        related_path = related_attr.split(".")
        inferred_backref = []
        mapper = sa.orm.class_mapper(entity_class)
        for attr in related_path:
            relation = mapper.relationships.get(attr)
            if not relation:
                msg = (
                    f'Invalid relation: "{related_attr}", invalid attribute is "{attr}"'
                )
                raise ValueError(msg)

            mapper = relation.mapper
            if inferred_backref is not None:
                try:
                    inferred_backref.append(relation.back_populates)
                except AttributeError:
                    inferred_backref = None

        try:
            meta.name = mapper.entity.__name__
        except AttributeError:
            return

        if not backref_attr:
            if inferred_backref is not None:
                backref_attr = ".".join(inferred_backref)
            else:
                msg = (
                    f"Audit setup class<{entity_class.__name__}: Could not guess backref name"
                    f' of relationship "{related_attr}", please use tuple annotation '
                    "on __auditable_entity__"
                )
                raise ValueError(msg)

        meta.related = related_path
        meta.backref_attr = backref_attr
        meta.enduser_ids = [attr_name.split(".") for attr_name in enduser_ids]

    def _get_changes_for(self, entity: Model) -> Changes:
        changes = getattr(entity, "__changes__", None)
        if not changes:
            changes = entity.__changes__ = Changes()
        return changes

    def set_attribute(
        self, entity: Model, new_value: Any, old_value: Any, initiator: Any
    ) -> None:
        attr_name = initiator.key
        if old_value == new_value:
            return

        # We don't log a few trivial cases so as not to overflow the audit log.
        if not old_value and not new_value:
            return

        changes = self._get_changes_for(entity)
        if attr_name in changes.columns:
            old_value = changes.columns[attr_name][0]

        # Hide content if needed (like password columns)
        # FIXME: we can only handle the simplest case: 1 attribute => 1 column
        columns = initiator.parent_token.columns
        if len(columns) == 1 and columns[0].info.get("audit_hide_content"):
            old_value = new_value = "******"

        old_value = format_large_value(old_value)
        new_value = format_large_value(new_value)
        changes.set_column_changes(attr_name, old_value, new_value)

    def collection_append(self, entity: Entity, value: Any, initiator: Any) -> None:
        changes = self._get_changes_for(entity)
        changes.collection_append(initiator.key, value)

    def collection_remove(self, entity: Entity, value: Any, initiator: Any) -> None:
        changes = self._get_changes_for(entity)
        changes.collection_remove(initiator.key, value)

    def create_audit_entries(
        self, session: Session, flush_context: UOWTransaction
    ) -> None:
        if not self.running or self.app_state.creating_entries:
            return

        self.app_state.creating_entries = True
        try:
            # An error here fails the flush: a change committed without its
            # audit entry would leave no trace of who made it.
            entries = []
            for identity_set, op in (
                (session.new, CREATION),
                (session.deleted, DELETION),
                (session.dirty, UPDATE),
            ):
                for model in identity_set:
                    entry = self.log(session, model, op)
                    if entry:
                        entries.append(entry)

                session.add_all(entries)
        finally:
            self.app_state.creating_entries = False

    def log(self, session: Session, model: Any, op_type: int) -> AuditEntry | None:
        if not self.is_auditable(model):
            return None

        entity = model
        # Nobody (a task, the CLI, a migration) is recorded as no user: the
        # admin panel shows it as "System".
        principal = get_current_principal()
        user_id = principal.id if principal is not None else None

        meta = model.__auditable__
        if meta.related:
            op_type |= RELATED
            entity = model
            for attr in meta.related:
                entity = getattr(entity, attr)
                if entity is None:
                    return None

        entry = AuditEntry(type=op_type, user_id=user_id)
        if op_type != DELETION:
            # DELETION|RELATED: deletion of a related model is ok: entity is still
            # here
            entry.entity = entity

        entry.entity_id = entity.id
        entry.entity_type = entity.entity_type

        entity_name = ""
        for attr_name in ("name", "path", "__path_before_delete"):
            if hasattr(entity, attr_name):
                entity_name = getattr(entity, attr_name)
        entry.entity_name = entity_name

        changes = Changes()
        op = entry.op
        if op == CREATION:
            for instrumented_attr in meta.audited_attrs:
                value = getattr(model, instrumented_attr.key)
                self.set_attribute(model, value, NEVER_SET, instrumented_attr.impl)

            for instrumented_attr in meta.collection_attrs:
                for obj in getattr(model, instrumented_attr.key):
                    self.collection_append(model, obj, instrumented_attr.impl)

            changes = getattr(model, "__changes__", changes)
        elif op == UPDATE:
            changes = getattr(model, "__changes__", changes)
            if not changes:
                return None

        if hasattr(model, "__changes__"):
            del model.__changes__

        if meta.related:
            enduser_ids = []
            for path in meta.enduser_ids:
                item = model
                for attr in path:
                    item = getattr(item, attr)
                enduser_ids.append(str(item))

            related_name = f"{meta.backref_attr} {' '.join(enduser_ids)}"
            related_changes = changes
            logger.debug(
                "related changes: {related_changes}",
                related_changes=repr(related_changes),
            )
            changes = Changes()
            changes.set_related_changes(related_name, related_changes)

        entry.changes = changes
        return entry

    def entries_for(self, entity, limit=None):
        query = AuditEntry.query.filter(AuditEntry.entity == entity).order_by(
            AuditEntry.happened_at.desc()
        )

        if limit is not None:
            query = query.limit(limit)

        return query.all()


audit_service = AuditService()


def format_large_value(value: Any) -> Any:
    with contextlib.suppress(TypeError):
        if len(value) > 1000:
            return "<<large value>>"
    return value


def get_model_changes(
    entity_type: str,
    *,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    hour: int | None = None,
    since: datetime | None = None,
) -> Query:
    """Get models modified at the given date with the Audit service.

    :param entity_type: string like "extranet_medicen.apps.crm.models.Compte".
      Beware the typo, there won't be a warning message.
    :param since: datetime
    :param year: int
    :param month: int
    :param day: int
    :param hour: int

    :returns: a query object
    """
    query = AuditEntry.query

    if since:
        query = query.filter(AuditEntry.happened_at >= since)

    if year:
        query = query.filter(extract("year", AuditEntry.happened_at) == year)
    if month:
        query = query.filter(extract("month", AuditEntry.happened_at) == month)
    if day:
        query = query.filter(extract("day", AuditEntry.happened_at) == day)
    if hour:
        query = query.filter(extract("hour", AuditEntry.happened_at) == hour)

    query = query.filter(AuditEntry.entity_type.like(entity_type)).order_by(
        AuditEntry.happened_at
    )

    return query


def get_columns_diff(changes):
    """Add the changed columns as a diff attribute.

    - changes: a list of changes (get_model_changes query.all())

    Return: the same list, to which elements we added a "diff"
    attribute containing the changed columns. Diff defaults to [].
    """
    for change in changes:
        change.diff = []
        elt_changes = change.get_changes()
        if elt_changes:
            change.diff = elt_changes.columns

    return changes
