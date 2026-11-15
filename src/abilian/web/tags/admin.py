# Copyright (c) 2012-2024, Abilian SAS

"""Admin panel for tags."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm
from flask import current_app, flash, redirect, render_template, request
from loguru import logger
from sqlalchemy.sql import functions as func

from abilian.core.entities import Entity
from abilian.core.extensions import db
from abilian.core.models.tag import Tag, entity_tag_tbl
from abilian.i18n import _, _l, _n
from abilian.services import get_service
from abilian.services.indexing.service import index_update
from abilian.web import url_for
from abilian.web.admin import AdminPanel
from abilian.web.views import ObjectEdit
from abilian.web.views.base import View

from .forms import TagForm

if TYPE_CHECKING:
    from collections.abc import Callable

_OBJ_COUNT = func.count(entity_tag_tbl.c.entity_id).label("obj_count")


def get_entities_for_reindex(tags):
    """Collect entities for theses tags."""
    if isinstance(tags, Tag):
        tags = (tags,)

    session = db.session()
    indexing = get_service("indexing")
    tbl = Entity.__table__
    tag_ids = [t.id for t in tags]
    query = (
        sa.sql.select(tbl.c.entity_type, tbl.c.id)
        .select_from(tbl.join(entity_tag_tbl, entity_tag_tbl.c.entity_id == tbl.c.id))
        .where(entity_tag_tbl.c.tag_id.in_(tag_ids))
    )

    entities = set()

    with session.no_autoflush:
        for entity_type, entity_id in session.execute(query):
            if entity_type not in indexing.adapted:
                logger.debug(
                    "{entity_type} is not indexed, skipping",
                    entity_type=repr(entity_type),
                )

            item = ("changed", entity_type, entity_id, ())
            entities.add(item)

    return entities


def schedule_entities_reindex(entities):
    """
    :param entities: as returned by :func:`get_entities_for_reindex`
    """
    entities = [(e[0], e[1], e[2], dict(e[3])) for e in entities]
    return index_update.send(index="default", items=entities)


class NSView(View):
    """View a Namespace."""

    def __init__(self, view_endpoint, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__selected_tags = None
        self.view_endpoint = view_endpoint

    def prepare_args(self, args, kwargs):
        self.ns = kwargs.get("ns")
        self.form_errors = {}
        return args, kwargs

    def get(self, ns):
        tags = (
            Tag.query.filter(Tag.ns == ns)
            .outerjoin(entity_tag_tbl, entity_tag_tbl.c.tag_id == Tag.id)
            .add_column(_OBJ_COUNT)
            .group_by(Tag)
            .order_by(sa.sql.func.lower(Tag.label))
        )

        # get a list of rows instead of (Tag, count) tuples
        tags = list(tags.session.execute(tags))
        return render_template(
            "admin/tags_ns.html",
            ns=ns,
            tags=tags,
            errors=self.form_errors,
            merge_to=request.form.get("merge_to", default="__None__", type=int),
            selected_tags={t.id for t in self._get_selected_tags()},
        )

    def redirect_to_view(self):
        return redirect(url_for(".tags_ns", ns=self.ns))

    def post(self, ns):
        data = request.form
        action = data.get("__action")

        match action:
            case "delete":
                return self.do_delete()
            case "merge":
                return self.do_merge()
            case _:
                flash(_("Unknown action"))
                return self.get(self.ns)

    def _get_selected_tags(self) -> list[Tag]:
        if self.__selected_tags is None:
            tag_ids = request.form.getlist("selected", type=int)
            if not tag_ids:
                self.__selected_tags = []
            else:
                self.__selected_tags = Tag.query.filter(
                    Tag.ns == self.ns, Tag.id.in_(tag_ids)
                ).all()

        return self.__selected_tags

    def do_delete(self):
        data = request.form
        confirm = data.get("confirm_delete", False, type=bool)

        if not confirm:
            flash(_("Please fix the error(s) below"), "error")
            self.form_errors["confirm_delete"] = _(
                "Must be checked to ensure you intent to delete these tags"
            )
            return self.get(self.ns)

        session = db.session()
        tags = self._get_selected_tags()

        if not tags:
            flash(_("No action performed: no tags selected"), "warning")
            return self.redirect_to_view()

        count = len(tags)
        entities_to_reindex = get_entities_for_reindex(tags)
        success_message = _n(
            "%(tag)s deleted",
            "%(num)d tags deleted:\n%(tags)s",
            count,
            tag=tags[0].label,
            tags=", ".join(t.label for t in tags),
        )
        for tag in tags:
            session.delete(tag)
        session.commit()
        flash(success_message)
        schedule_entities_reindex(entities_to_reindex)
        return self.redirect_to_view()

    def do_merge(self):
        target_id = request.form.get("merge_to", type=int)

        if not target_id:
            flash(_("You must select a target tag to merge to"), "error")
            return self.get(self.ns)

        target = Tag.query.filter(Tag.ns == self.ns, Tag.id == target_id).scalar()

        if not target:
            flash(_("Target tag not found, no action performed"), "error")
            return self.get(self.ns)

        merge_from = set(self._get_selected_tags())
        merge_from.discard(target)

        if not merge_from:
            flash(_("No tag selected for merging"), "warning")
            return self.get(self.ns)

        session = db.session()
        merge_from_ids = [t.id for t in merge_from]
        tbl = entity_tag_tbl
        entities_to_reindex = get_entities_for_reindex(merge_from)
        already_tagged = sa.sql.select(tbl.c.entity_id).where(tbl.c.tag_id == target.id)
        del_dup = tbl.delete().where(
            sa.sql.and_(
                tbl.c.tag_id.in_(merge_from_ids), tbl.c.entity_id.in_(already_tagged)
            )
        )
        session.execute(del_dup)
        update = (
            tbl.update()
            .where(tbl.c.tag_id.in_(merge_from_ids))
            .values(tag_id=target.id)
        )
        session.execute(update)
        for merged in merge_from:
            session.delete(merged)
        session.commit()
        schedule_entities_reindex(entities_to_reindex)
        return self.redirect_to_view()


class BaseTagView:
    """Mixin for tag views."""

    Model = Tag
    Form = TagForm

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.extension = current_app.extensions["tags"]

    def prepare_args(self, args, kwargs):
        self.ns = kwargs.pop("ns")
        return super().prepare_args(args, kwargs)

    def view_url(self):
        return url_for(".tags_ns", ns=self.ns)

    def index_url(self):
        return self.view_url()


class TagEdit(BaseTagView, ObjectEdit[Tag, TagForm]):
    _message_success = _l("Tag edited")
    has_changes = False
    _entities_to_reindex: list[Entity] = []

    def after_populate_obj(self) -> None:
        session = sa.orm.object_session(self.obj)
        self.has_changes = self.obj in (session.dirty | session.deleted)
        if self.has_changes:
            # since the tag may be in pending-delete, we must collect them
            # before flush
            self._entities_to_reindex = get_entities_for_reindex(self.obj)

    def commit_success(self) -> None:
        if not (self.has_changes and self._entities_to_reindex):
            return

        schedule_entities_reindex(self._entities_to_reindex)


class TagPanel(AdminPanel):
    """Tags administration."""

    id = "tags"
    label = _l("Tags")
    icon = "tags"

    def get(self):
        obj_count = (
            sa.sql.select(
                Tag.ns,
                func.count(entity_tag_tbl.c.entity_id).label("obj_count"),
            )
            .select_from(Tag.__table__.join(entity_tag_tbl))
            .group_by(Tag.ns)
            .alias()
        )

        ns_query = (
            sa.sql.select(
                Tag.ns, func.count(Tag.id).label("tag_count"), obj_count.c.obj_count
            )
            .select_from(Tag.__table__.outerjoin(obj_count, Tag.ns == obj_count.c.ns))
            .group_by(Tag.ns, obj_count.c.obj_count)
            .order_by(Tag.ns)
        )

        session = db.session()
        namespaces = session.execute(ns_query)

        return render_template("admin/tags.html", namespaces=namespaces)

    def install_additional_rules(self, add_url_rule: Callable) -> None:
        panel_endpoint = f".{self.id}"
        ns_base = "/<string:ns>/"
        add_url_rule(
            ns_base,
            endpoint="ns",
            view_func=NSView.as_view("ns", view_endpoint=panel_endpoint),
        )

        tag_base = f"{ns_base}<int:object_id>/"
        add_url_rule(
            tag_base,
            endpoint="tag_edit",
            view_func=TagEdit.as_view("tag_edit", view_endpoint=panel_endpoint),
        )

        add_url_rule(
            f"{tag_base}delete",
            endpoint="tag_delete",
            view_func=TagEdit.as_view("tag_delete", view_endpoint=panel_endpoint),
        )
