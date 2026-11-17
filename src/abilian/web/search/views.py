# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import operator
from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import whoosh
import whoosh.highlight
import whoosh.searching
import whoosh.sorting
from flask import current_app, g, render_template, request, url_for
from whoosh import query as wq

from abilian.core.entities import Entity
from abilian.core.extensions.login import authenticated, authenticated_user
from abilian.core.util import utcnow
from abilian.i18n import _, _l
from abilian.services import get_service
from abilian.services.security import AUTHENTICATED
from abilian.web import views
from abilian.web.access_blueprint import AccessControlBlueprint
from abilian.web.action import Endpoint
from abilian.web.nav import BreadcrumbItem

if TYPE_CHECKING:
    from abilian.core.models.subjects import User

BOOTSTRAP_MARKUP_HIGHLIGHTER = whoosh.highlight.HtmlFormatter(
    tagname="mark", classname="", termclass="term-", between="[…]"
)

RESULTS_FRAGMENTER = whoosh.highlight.SentenceFragmenter()

#
# Some hardcoded settings (for now)
#
PAGE_SIZE = 20
MAX_LIVE_RESULTS_PER_CLASS = 5

search = AccessControlBlueprint(
    "search",
    __name__,
    url_prefix="/search",
    template_folder="templates",
    allowed_roles=AUTHENTICATED,
)
route = search.route


def friendly_fqcn(fqcn):
    return fqcn.rsplit(".", 1)[-1]


@search.url_value_preprocessor
def init_search(endpoint, values) -> None:
    q = request.args.get("q", "")
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except Exception:
        page = 1

    g.breadcrumb.append(
        BreadcrumbItem(
            label=f'"{q}"', icon="search", url=Endpoint("search.search_main", q=q)
        )
    )

    page_kw = OrderedDict(q=q)
    object_types = request.args.getlist("object_type")

    if object_types:
        page_kw["object_type"] = object_types
        g.breadcrumb.append(
            BreadcrumbItem(
                label=" | ".join(friendly_fqcn(name) for name in object_types),
                url=Endpoint("search.search_main", **page_kw),
            )
        )

    if page > 1:
        g.breadcrumb.append(
            BreadcrumbItem(
                label=str(page),
                url=Endpoint("search.search_main", page=page, **page_kw),
            )
        )

    values["q"] = q
    values["page"] = page


@search.context_processor
def install_hit_to_url():
    return {"url_for_hit": current_app.extensions["indexing"].url_for_hit}


_COUNT_OBJECT_TYPE_FACET = whoosh.sorting.FieldFacet(
    "object_type", maptype=whoosh.sorting.Count
)
#: The index fields SBE adds to community content (`sbe/apps/communities/search.py`),
#: and its communities' type, named rather than imported: Abilian Core imports none
#: of SBE.
_COUNT_COMMUNITY_FACET = whoosh.sorting.FieldFacet(
    "community_id", maptype=whoosh.sorting.Count
)
COMMUNITY_TYPE = "abilian.sbe.apps.communities.models.Community"

#: What each kind of result is called on the page, by its class name; another kind
#: keeps its class name.
KIND_LABELS = {
    "Thread": _l("Discussions"),
    "Document": _l("Documents"),
    "Folder": _l("Folders"),
    "WikiPage": _l("Wiki"),
    "User": _l("People"),
    "Community": _l("Communities"),
}

#: How far back a search may look: its parameter, its label, its length.
PERIODS = (
    ("30d", _l("In the last 30 days"), timedelta(days=30)),
    ("year", _l("In the last year"), timedelta(days=365)),
)


@dataclass(frozen=True)
class Choice:
    """A way to narrow the results, as a link: what it says, how many, where."""

    label: str
    count: int | None
    url: str
    active: bool


@route("")
@authenticated
def search_main(user: User, q="", page=1):
    """Results for `q`, narrowed by kind, community and period, a page at a time."""
    svc = get_service("indexing")
    q = q.strip()
    scope = request.args.get("community", "")
    since = request.args.get("since", "")
    object_types = sorted(request.args.getlist("object_type"))
    params = {"q": q, "object_type": object_types, "community": scope, "since": since}

    def url(**changes) -> str:
        kw = {k: v for k, v in {**params, **changes}.items() if v}
        return url_for(".search_main", **kw)

    period = next((p for p in PERIODS if p[0] == since), None)
    recent = wq.DateRange("updated_at", utcnow() - period[2], None) if period else None
    in_scope = wq.Term("community_slug", scope) if scope else None

    def run(*filters, types=()):
        """The search, narrowed by what is given, counted by kind and community."""
        kept = [f for f in filters if f is not None]
        return svc.search(
            q,
            user=user,
            object_types=types,
            limit=page * PAGE_SIZE,
            groupedby={
                "object_type": _COUNT_OBJECT_TYPE_FACET,
                "community_id": _COUNT_COMMUNITY_FACET,
            },
            filter=wq.And(kept) if len(kept) > 1 else (kept[0] if kept else None),
        )

    # Counted before the kind is chosen, so each kind says what choosing it gives.
    unfiltered = run(in_scope, recent)
    by_type = _groups(unfiltered, "object_type")
    kinds = [
        Choice(str(_("All")), len(unfiltered), url(object_type=()), not object_types)
    ]
    kinds += sorted(
        (
            Choice(
                str(KIND_LABELS.get(friendly_fqcn(name), friendly_fqcn(name))),
                count,
                url(object_type=[name]),
                name in object_types,
            )
            for name, count in by_type.items()
        ),
        key=operator.attrgetter("label"),
    )

    # Where else the same words are: the communities, with the scope set aside.
    everywhere = run(recent, types=object_types) if scope else unfiltered
    community_counts = _groups(everywhere, "community_id")
    results = run(in_scope, recent, types=object_types) if object_types else unfiltered

    results.formatter = BOOTSTRAP_MARKUP_HIGHLIGHTER
    results.fragmenter = RESULTS_FRAGMENTER
    results_count = len(results)
    pagecount = max(1, -(-results_count // PAGE_SIZE))
    page = min(page, pagecount)
    results = whoosh.searching.ResultsPage(results, page, PAGE_SIZE)

    ids = set(community_counts) | {hit.get("community_id") for hit in results}
    communities = {
        c.id: c for c in Entity.query.filter(Entity.id.in_(ids - {None})).all()
    }
    # Looked up on its own: a search with no result in it still says where it looked.
    scope_community = (
        Entity.query.filter(
            Entity.slug == scope, Entity._entity_type == COMMUNITY_TYPE
        ).first()
        if scope
        else None
    )
    elsewhere = sorted(
        (
            (communities[cid], count, url(community=communities[cid].slug))
            for cid, count in community_counts.items()
            if cid in communities and communities[cid] is not scope_community
        ),
        key=lambda row: -row[1],
    )

    ctx = {
        "q": q,
        "results": results,
        "results_count": results_count,
        "kinds": kinds,
        "scope": scope_community,
        "everywhere_url": url(community=""),
        "everywhere_count": len(everywhere) if scope else None,
        "elsewhere": elsewhere,
        "periods": [Choice(str(_("Any time")), None, url(since=""), not period)]
        + [
            Choice(str(label), None, url(since=key), key == since)
            for key, label, _d in PERIODS
        ],
        "communities": communities,
        "pages": [
            (n, url(page=n))
            for n in range(max(page - 2, 1), min(page + 4, pagecount) + 1)
        ],
        "prev_page": url(page=page - 1) if page > 1 else None,
        "next_page": url(page=page + 1) if page < pagecount else None,
        "friendly_fqcn": friendly_fqcn,
    }
    return render_template("search/search.html", **ctx)


def _groups(results, name: str) -> dict:
    """A facet's counts, or none when nothing was indexed with it."""
    try:
        return {k: v for k, v in results.groups(name).items() if k is not None}
    except KeyError:
        return {}


class Live(views.JSONView):
    """JSON response for live search."""

    def data(self, q="", page=None, *args, **kwargs):
        if not q:
            q = ""
        svc = get_service("indexing")
        url_for_hit = svc.app_state.url_for_hit
        search_kwargs = {"facet_by_type": True}
        results = svc.search(q, user=authenticated_user(), **search_kwargs)
        datasets = {}

        for typename, docs in results.items():
            dataset = []
            for doc in docs:
                # Because it happens sometimes
                try:
                    name = doc["name"]
                except KeyError:
                    continue

                d = {"name": name}
                url = url_for_hit(doc, None)
                if url is not None:
                    d["url"] = url
                    dataset.append(d)
            datasets[typename] = dataset

        return {"results": datasets}


route("/live")(Live.as_view("live"))
