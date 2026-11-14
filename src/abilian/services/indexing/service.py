# Copyright (c) 2012-2024, Abilian SAS

"""Indexing service for Abilian.

Adds Whoosh indexing capabilities to SQLAlchemy models.

Based on Flask-whooshalchemy by Karl Gyllstrom.

:copyright: (c) 2013-2019 by Abilian SAS
:copyright: (c) 2012 by Stefane Fermigier
:copyright: (c) 2012 by Karl Gyllstrom
:license: BSD (see LICENSE.txt)
"""

from __future__ import annotations

import contextlib
import os
from inspect import isclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from flask import Flask, appcontext_pushed, current_app, g
from flask_login import current_user
from loguru import logger
from sqlalchemy import event
from sqlalchemy.orm import Session
from whoosh import query as wq
from whoosh.filedb.filestore import FileStorage, RamStorage
from whoosh.index import FileIndex, Index
from whoosh.qparser import DisMaxParser
from whoosh.writing import CLEAR, AsyncWriter

from abilian.core import signals
from abilian.core.application import as_application
from abilian.core.dramatiq.singleton import dramatiq
from abilian.core.entities import Entity, Indexable
from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User
from abilian.core.util import fqcn as base_fqcn, friendly_fqcn, unwrap
from abilian.services import Service, ServiceState
from abilian.services.security import (
    ANONYMOUS,
    AUTHENTICATED,
    Role,
    is_site_admin,
    security,
)

from .adapter import SAAdapter
from .schema import DefaultSearchSchema, indexable_role

if TYPE_CHECKING:
    from collections.abc import Collection

    from sqlalchemy.orm.unitofwork import UOWTransaction

    from abilian.app import Application
    from abilian.core.models import Model

PENDING_INDEXATION_ATTR = "abilian_pending_indexation"


def url_for_hit(hit, default="#"):
    """Helper for building URLs from results."""
    try:
        object_type = hit["object_type"]
        object_id = int(hit["id"])
        return as_application(current_app).default_view.url_for(
            hit, object_type, object_id
        )
    except KeyError:
        return default
    except Exception:
        logger.opt(exception=True).error("Error building URL for search result")
        return default


def fqcn(cls: Any) -> str:
    if issubclass(cls, Entity):
        return cls.entity_type
    return base_fqcn(cls)


class IndexServiceState(ServiceState):
    def __init__(self, service: WhooshIndexService, *args: Any, **kwargs: Any) -> None:
        super().__init__(service, *args, **kwargs)
        self.whoosh_base = None
        self.indexes: dict[str, Index] = {}
        self.indexed_classes: set[type] = set()
        self.indexed_fqcn: set[str] = set()
        self.search_filter_funcs = []
        self.value_provider_funcs = []
        self.url_for_hit = url_for_hit

    @property
    def to_update(self) -> list[tuple[str, Entity]]:
        if not hasattr(g, PENDING_INDEXATION_ATTR):
            values: list[tuple[str, Entity]] = []
            setattr(g, PENDING_INDEXATION_ATTR, values)
        return getattr(g, PENDING_INDEXATION_ATTR)

    @to_update.setter
    def to_update(self, values: list[tuple[str, Entity]]) -> None:
        setattr(g, PENDING_INDEXATION_ATTR, values)


class WhooshIndexService(Service):
    """Index documents using whoosh."""

    name = "indexing"
    AppStateClass = IndexServiceState

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.adapters_cls = [SAAdapter]
        self.adapted = {}
        self.schemas = {"default": DefaultSearchSchema()}
        self._listening = False

    def init_app(self, app: Application) -> None:
        super().init_app(app)
        state = app.extensions[self.name]

        whoosh_base = Path(app.config.get("WHOOSH_BASE", "whoosh"))

        if not whoosh_base.is_absolute():
            whoosh_base = Path(app.instance_path) / whoosh_base

        if not whoosh_base.is_dir():
            whoosh_base.mkdir(parents=True)

        state.whoosh_base = str(whoosh_base.resolve())

        if not self._listening:
            event.listen(Session, "after_flush", self.after_flush)
            event.listen(Session, "after_commit", self.after_commit)
            self._listening = True

        appcontext_pushed.connect(self.clear_update_queue, app)
        signals.register_js_api.connect(self._do_register_js_api)

    def _do_register_js_api(self, sender: Application) -> None:
        app = sender
        js_api = app.js_api.setdefault("search", {})
        js_api["object_types"] = self.searchable_object_types()

    def register_search_filter(self, func) -> None:
        """Register a filter narrowing search results for one user.

        Called as `func(user)` and And'ed with the other filters; return None to
        add nothing. The user is passed rather than read from the request, so a
        filter is callable outside one and its dependencies are in its
        signature.

        A filter is not asked to consider whether the user may see everything
        anyway: `search` settles that once, before calling any of them. Both
        this and the role filter below used to make that decision separately,
        off `g.is_manager`, which is how one of them came to be written without
        the guard.
        """
        self.app_state.search_filter_funcs.append(func)

    def register_value_provider(self, func) -> None:
        """Register a function that may alter content of indexable document.

        It is used in :meth:`get_document` and called after adapter has built
        document.

        The function must accept (document, obj) as arguments, and return
        the new document object.
        """
        self.app_state.value_provider_funcs.append(func)

    def clear_update_queue(self, app: Flask | None = None) -> None:
        self.app_state.to_update = []

    def start(self, ignore_state: bool = False) -> None:
        super().start(ignore_state)
        self.register_classes()
        self.init_indexes()
        self.clear_update_queue()

    def init_indexes(self) -> None:
        """Create indexes for schemas."""
        state = self.app_state

        for name, schema in self.schemas.items():
            if current_app.testing:
                storage = TestingStorage()
            else:
                index_path = (Path(state.whoosh_base) / name).absolute()
                if not index_path.exists():
                    index_path.mkdir(parents=True)
                storage = FileStorage(str(index_path))

            if storage.index_exists(name):
                index = FileIndex(storage, schema, name)
            else:
                index = FileIndex.create(storage, schema, name)

            state.indexes[name] = index

    def clear(self) -> None:
        """Remove all content from indexes, and unregister all classes.

        After clear() the service is stopped. It must be started again
        to create new indexes and register classes.
        """
        logger.info("Resetting indexes")
        state = self.app_state

        for idx in state.indexes.values():
            writer = AsyncWriter(idx)
            writer.commit(merge=True, optimize=True, mergetype=CLEAR)

        state.indexes.clear()
        state.indexed_classes.clear()
        state.indexed_fqcn.clear()
        self.clear_update_queue()

        if self.running:
            self.stop()

    def index(self, name: str = "default") -> Index:
        return self.app_state.indexes[name]

    @property
    def default_search_fields(self) -> dict[str, float]:
        """Return default field names and boosts to be used for searching.

        Can be configured with `SEARCH_DEFAULT_BOOSTS`
        """
        config = current_app.config.get("SEARCH_DEFAULT_BOOSTS")
        if not config:
            config = {"name": 1.5, "name_prefix": 1.3, "description": 1.3, "text": 1.0}
        return config

    def searchable_object_types(self) -> list:
        """List of (object_types, friendly name) present in the index."""
        try:
            idx = self.index()
        except KeyError:
            # index does not exists: service never started, may happens during
            # tests
            return []

        with idx.reader() as r:
            indexed = sorted(set(r.field_terms("object_type")))
        app_indexed = self.app_state.indexed_fqcn

        return [(name, friendly_fqcn(name)) for name in indexed if name in app_indexed]

    def search(
        self,
        q: str,
        *,
        index_name: str = "default",
        fields: dict[str, float] | None = None,
        Models: Collection[type[Model]] = (),
        object_types: Collection[str] = (),
        prefix: bool = True,
        facet_by_type: bool = False,
        user: User | None = None,
        **search_args,
    ):
        """Interface to search indexes.

        :param q: unparsed search string.
        :param index_name: name of index to use for search.
        :param fields: optionnal mapping of field names -> boost factor?
        :param Models: list of Model classes to limit search on.
        :param object_types: same as `Models`, but directly the model string.
        :param prefix: enable or disable search by prefix
        :param facet_by_type: if set, returns a dict of object_type: results with a
             max of `limit` matches for each type.
        :param search_args: any valid parameter for
            :meth:`whoosh.searching.Search.search`. This includes `limit`,
            `groupedby` and `sortedby`
        """
        index = self.app_state.indexes[index_name]
        if not fields:
            fields = self.default_search_fields

        valid_fields = {
            f
            for f in index.schema.names(check_names=fields)
            if prefix or not f.endswith("_prefix")
        }

        for invalid in set(fields) - valid_fields:
            del fields[invalid]

        parser = DisMaxParser(fields, index.schema)
        query = parser.parse(q)

        filters = search_args.setdefault("filter", None)
        filters = [filters] if filters is not None else []
        del search_args["filter"]

        if user is None:
            user = current_user
        user = unwrap(user)

        # One decision for every filter below: a site administrator sees
        # everything, so none of them are applied.
        if not is_site_admin(user):
            # security access filter
            roles = {indexable_role(user)}
            if not user.is_anonymous:
                roles.add(indexable_role(ANONYMOUS))
                roles.add(indexable_role(AUTHENTICATED))
                roles |= {indexable_role(r) for r in security.get_roles(user)}

            filter_q = wq.Or(
                [wq.Term("allowed_roles_and_users", role) for role in roles]
            )
            filters.append(filter_q)

            for func in self.app_state.search_filter_funcs:
                filter_q = func(user)
                if filter_q is not None:
                    filters.append(filter_q)

        object_types_set = set(object_types)
        for m in Models:
            object_type = m.entity_type
            if not object_type:
                continue
            object_types_set.add(object_type)

        if object_types_set:
            object_types_set &= self.app_state.indexed_fqcn
        else:
            # ensure we don't show content types previously indexed but not yet
            # cleaned from index
            object_types_set = self.app_state.indexed_fqcn

        # limit object_type
        filter_q = wq.Or([wq.Term("object_type", t) for t in object_types_set])
        filters.append(filter_q)

        if filters:
            filter_q = wq.And(filters) if len(filters) > 1 else filters[0]
            # search_args['filter'] = filter_q
            query = filter_q & query

        if facet_by_type:
            if not object_types_set:
                object_types_set = {t[0] for t in self.searchable_object_types()}

            # limit number of documents to score, per object type
            collapse_limit = 5
            search_args["groupedby"] = "object_type"
            search_args["collapse"] = "object_type"
            search_args["collapse_limit"] = collapse_limit
            search_args["limit"] = collapse_limit * max(len(object_types_set), 1)

        with index.searcher(closereader=False) as searcher:
            # 'closereader' is needed, else results cannot by used outside 'with'
            # statement
            results = searcher.search(query, **search_args)

            if facet_by_type:
                positions = {
                    doc_id: pos
                    for pos, doc_id in enumerate(i[1] for i in results.top_n)
                }
                sr = results
                results = {}
                for typename, doc_ids in sr.groups("object_type").items():
                    results[typename] = [
                        sr[positions[oid]] for oid in doc_ids[:collapse_limit]
                    ]

            return results

    def search_for_class(self, query, cls, index="default", **search_args):
        return self.search(query, Models=(fqcn(cls),), index=index, **search_args)

    def register_classes(self) -> None:
        state = self.app_state
        classes = (
            cls
            for cls in db.Model.registry._class_registry.values()
            if isclass(cls) and issubclass(cls, Indexable) and cls.__indexable__
        )
        for cls in classes:
            if cls not in state.indexed_classes:
                self.register_class(cls, app_state=state)

    def register_class(
        self, cls: type, app_state: IndexServiceState | None = None
    ) -> None:
        """Register a model class."""
        state = app_state if app_state is not None else self.app_state

        for Adapter in self.adapters_cls:
            if Adapter.can_adapt(cls):
                break
        else:
            return

        cls_fqcn = fqcn(cls)
        self.adapted[cls_fqcn] = Adapter(cls, self.schemas["default"])
        state.indexed_classes.add(cls)
        state.indexed_fqcn.add(cls_fqcn)

    def after_flush(self, session: Session, flush_context: UOWTransaction) -> None:
        if not self.running or session is not db.session():
            return

        to_update = self.app_state.to_update
        session_objs = (
            ("new", session.new),
            ("deleted", session.deleted),
            ("changed", session.dirty),
        )
        for key, objs in session_objs:
            for obj in objs:
                model_name = fqcn(obj.__class__)
                adapter = self.adapted.get(model_name)

                if adapter is None or not adapter.indexable:
                    continue

                to_update.append((key, obj))

    def after_commit(self, session: Session) -> None:
        """Any db updates go through here.

        We check if any of these models have ``__searchable__`` fields,
        indicating they need to be indexed. With these we update the
        whoosh index for the model. If no index exists, it will be
        created here; this could impose a penalty on the initial commit
        of a model.
        """
        if (
            not self.running
            or session.transaction.nested  # inside a sub-transaction:
            # not yet written in DB
            or session is not db.session()
        ):
            # note: we have not tested too far if session is enclosed in a transaction
            # at connection level. For now it's not a standard use case, it would most
            # likely happens during tests (which don't do that for now)
            return

        primary_field = "id"
        state = self.app_state
        items: list[tuple[str, str, int, dict]] = []
        for op, obj in state.to_update:
            model_name = fqcn(obj.__class__)
            if model_name not in self.adapted or not self.adapted[model_name].indexable:
                # safeguard
                continue

            # safeguard against DetachedInstanceError
            if sa.orm.object_session(obj) is not None:
                items.append((op, model_name, getattr(obj, primary_field), {}))

        if items:
            logger.debug("after_commit() items={items}", items=items)
            if os.environ.get("TESTING_DIRECT_FUNCTION_CALL"):
                index_update(index="default", items=items)
            else:
                # productioncall: async dramatiq actor
                index_update.send(index="default", items=items)

        self.clear_update_queue()

    def get_document(
        self, obj: Entity, adapter: SAAdapter | None = None
    ) -> dict[str, Any]:
        if adapter is None:
            class_name = fqcn(obj.__class__)
            adapter = self.adapted.get(class_name)

        if adapter is None or not adapter.indexable:
            return {}

        document = adapter.get_document(obj)

        for k, v in document.items():
            match v:
                case None:
                    del document[k]
                    continue
                case User() | Group() | Role():
                    document[k] = indexable_role(v)

        if not document.get("allowed_roles_and_users"):
            # no data for security: assume anybody can access the document
            document["allowed_roles_and_users"] = indexable_role(ANONYMOUS)

        for func in self.app_state.value_provider_funcs:
            res = func(document, obj)
            if res is not None:
                document = res

        return document

    def index_objects(self, objects, index="default") -> None:
        """Bulk index a list of objects."""
        if not objects:
            return

        index_name = index
        index = self.app_state.indexes[index_name]
        indexed = set()

        with index.writer() as writer:
            for obj in objects:
                document = self.get_document(obj)
                if not document:
                    continue

                object_key = document["object_key"]
                if object_key in indexed:
                    continue

                writer.delete_by_term("object_key", object_key)
                try:
                    writer.add_document(**document)
                except ValueError:
                    # logger is here to give us more infos in order to catch a weird bug
                    # that happens regularly on CI but is not reliably
                    # reproductible.
                    logger.opt(exception=True).error(
                        "writer.add_document({document})",
                        document=repr(document),
                    )
                    raise
                indexed.add(object_key)


service = WhooshIndexService()


@dramatiq.actor
def index_update(index: str, items: list[tuple[str, str, int, dict]]) -> None:
    """
    :param:index: index name
    :param:items: list of (operation, full class name, primary key, data) tuples.
    """

    logger.debug("index_update() actor : index={index}", index=index)

    index_name = index
    index = service.app_state.indexes[index_name]
    adapted = service.adapted

    # session = safe_session()
    session = Session(bind=db.session.get_bind(None, None))
    updated = set()
    writer = AsyncWriter(index)
    try:
        for op, cls_name, pk, data in items:
            if pk is None:
                continue

            # always delete. Whoosh manual says that 'update' is actually delete + add
            # operation
            object_key = f"{cls_name}:{pk}"
            writer.delete_by_term("object_key", object_key)

            adapter = adapted.get(cls_name)
            if not adapter:
                # FIXME: log to sentry?
                continue

            if object_key in updated:
                # don't add twice the same document in same transaction. The writer will
                # not delete previous records, ending in duplicate records for same
                # document.
                continue

            if op in ("new", "changed"):
                with session.begin(nested=True):
                    obj = adapter.retrieve(pk, _session=session, **data)

                if obj is None:
                    # deleted after task queued, but before task run
                    continue

                document = service.get_document(obj, adapter)
                try:
                    writer.add_document(**document)
                except ValueError:
                    # logger is here to give us more infos in order to catch a weird bug
                    # that happens regularly on CI but is not reliably
                    # reproductible.
                    logger.opt(exception=True).error(
                        "writer.add_document({document})",
                        document=repr(document),
                    )
                    raise
                updated.add(object_key)
    except Exception:
        writer.cancel()
        raise

    session.close()
    writer.commit()

    # Exception may happen when actual writer was already available:
    # asyncwriter didn't need to start a thread
    with contextlib.suppress(RuntimeError):
        # async thread: wait for its termination
        writer.join()


class TestingStorage(RamStorage):
    """RamStorage whoses temp_storage method returns another TestingStorage
    instead of a FileStorage.

    Reason is that FileStorage.temp_storage() creates temp file in

    /tmp/index_name.tmp/, which is subject to race conditions when many
    tests are ran in parallel, including different abilian-based packages.
    """

    def temp_storage(self, name: str | None = None) -> TestingStorage:
        return TestingStorage()
