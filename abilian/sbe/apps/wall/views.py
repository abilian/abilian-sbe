from datetime import date
from itertools import groupby, islice
from typing import Any, Dict

import whoosh
import whoosh.query as wq
from flask import current_app, g, render_template
from flask_babel import format_date
from sqlalchemy.orm import joinedload

from abilian.sbe.apps.communities.blueprint import Blueprint
from abilian.sbe.apps.documents.models import Document, icon_for
from abilian.sbe.apps.forum.models import Thread
from abilian.services import get_service
from abilian.web import url_for
from abilian.web.action import actions

from .presenters import ActivityEntryPresenter
from .util import get_recent_entries

wall = Blueprint("wall", __name__, url_prefix="/wall", template_folder="templates")
route = wall.route


@wall.url_value_preprocessor
def set_current_tab(endpoint: str, values: Dict[Any, Any]) -> None:
    g.current_tab = "wall"


@route("/")
def index() -> str:
    actions.context["object"] = g.community._model
    entries = get_recent_entries(20, community=g.community)
    entries = ActivityEntryPresenter.wrap_collection(entries)
    return render_template("wall/index.html", entries=entries)


@route("/files")
def files():
    community = g.community._model
    actions.context["object"] = community

    all_files = []
    if community.has_forum:
        all_files += get_attachments_from_forum(community)

    if community.has_documents:
        all_files += get_attachments_from_dms(community)

    all_files = sorted(all_files, key=lambda doc: doc.date)
    all_files = islice(reversed(all_files), 0, 50)
    grouped_docs = group_monthly(all_files)

    return render_template("wall/files.html", grouped_docs=grouped_docs)


class Attachment:
    def __init__(self, url, name, owner, date, content_length, content_type):
        self.url = url
        self.name = name
        self.owner = owner
        self.date = date
        self.content_length = content_length
        self.content_type = content_type

    @property
    def icon(self):
        return icon_for(self.content_type)


def get_attachments_from_forum(community):
    all_threads = (
        Thread.query.filter(Thread.community_id == community.id)
        .options(joinedload("posts"))
        .options(joinedload("posts.attachments"))
        .order_by(Thread.created_at.desc())
        .all()
    )

    posts_with_attachments = []
    for thread in all_threads:
        for post in thread.posts:
            if getattr(post, "attachments", None):
                posts_with_attachments.append(post)

    posts_with_attachments.sort(key=lambda post: post.created_at)
    posts_with_attachments.reverse()

    attachments = []
    for post in posts_with_attachments:
        for att in post.attachments:
            url = current_app.default_view.url_for(att)
            attachment = Attachment(
                url,
                att.name,
                str(att.owner),
                att.created_at,
                att.content_length,
                att.content_type,
            )
            attachments.append(attachment)

    return attachments


# FIXME: significant performance issues here, needs major refactoring
def get_attachments_from_dms(community):
    index_service = get_service("indexing")
    filters = wq.And(
        [
            wq.Term("community_id", community.id),
            wq.Term("object_type", Document.entity_type),
        ]
    )
    sortedby = whoosh.sorting.FieldFacet("created_at", reverse=True)
    documents = index_service.search("", filter=filters, sortedby=sortedby, limit=50)

    attachments = []
    for doc in documents:
        url = url_for(doc)
        attachment = Attachment(
            url,
            doc["name"],
            doc["owner_name"],
            doc["created_at"],
            doc.get("content_length"),
            doc.get("content_type", ""),
        )
        attachments.append(attachment)

    return attachments


# FIXME: copy/pasted then hacked from forum/views.py
def group_monthly(objects):
    # We're using Python's groupby instead of SA's group_by here
    # because it's easier to support both SQLite and Postgres this way.
    def grouper(entity):
        return entity.date.year, entity.date.month

    def format_month(year, month):
        month = format_date(date(year, month, 1), "MMMM").capitalize()
        return f"{month} {year}"

    grouped = groupby(objects, grouper)
    grouped = [
        (format_month(year, month), list(objs)) for (year, month), objs in grouped
    ]
    return grouped
