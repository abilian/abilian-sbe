# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import operator
from collections import OrderedDict
from functools import partial

import whoosh
import whoosh.highlight
import whoosh.searching
import whoosh.sorting
from flask import Blueprint, current_app, g, render_template, request, url_for

from abilian.i18n import _
from abilian.services import get_service
from abilian.web import views
from abilian.web.action import Endpoint
from abilian.web.nav import BreadcrumbItem

BOOTSTRAP_MARKUP_HIGHLIGHTER = whoosh.highlight.HtmlFormatter(
    tagname="mark", classname="", termclass="term-", between="[…]"
)

RESULTS_FRAGMENTER = whoosh.highlight.SentenceFragmenter()

#
# Some hardcoded settings (for now)
#
PAGE_SIZE = 20
MAX_LIVE_RESULTS_PER_CLASS = 5

search = Blueprint(
    "search", __name__, url_prefix="/search", template_folder="templates"
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


@route("")
def search_main(q="", page=1):
    svc = get_service("indexing")
    q = q.strip()
    page = int(request.args.get("page", page))
    search_kwargs = {"limit": page * PAGE_SIZE}
    page_url_kw = OrderedDict(q=q)

    search_kwargs["groupedby"] = _COUNT_OBJECT_TYPE_FACET
    results = svc.search(q, **search_kwargs)

    filtered_by_type = sorted(request.args.getlist("object_type"))
    if filtered_by_type:
        page_url_kw["object_type"] = filtered_by_type

    page_url = partial(url_for, ".search_main", **page_url_kw)

    # get facets groups
    by_object_type = []
    try:
        facet_group = results.groups("object_type")
    except KeyError:
        pass
    else:
        for typename, count in facet_group.items():
            is_active = typename in filtered_by_type
            classname = friendly_fqcn(typename)
            link = page_url(object_type=typename)
            by_object_type.append((classname, count, link, is_active))

        by_object_type.sort(key=operator.itemgetter(0))

    if by_object_type:
        # Insert 'all' to clear all filters
        is_active = len(filtered_by_type) == 0
        all_types = (_("All"), len(results), page_url(object_type=()), is_active)
        by_object_type.insert(0, all_types)

    if filtered_by_type:
        # FIXME: sanitize input
        results = svc.search(q, object_types=filtered_by_type, **search_kwargs)

    results.formatter = BOOTSTRAP_MARKUP_HIGHLIGHTER
    results.fragmenter = RESULTS_FRAGMENTER

    # paginate results
    results_count = len(results)

    # results.pagecount must be ignored when query is filtered: it ignores
    # filtered_count
    pagecount = 1 + results_count // PAGE_SIZE
    page = min(page, pagecount)
    results = whoosh.searching.ResultsPage(results, page, PAGE_SIZE)
    page = results.pagenum
    first_page = page_url(page=1)
    last_page = page_url(page=pagecount)
    prev_page = page_url(page=page - 1) if page > 1 else None
    next_page = page_url(page=page + 1) if page < pagecount else None

    page_min = max(page - 2, 1)
    page_max = min(page + 4, pagecount)
    next_pages_numbered = [
        (index, page_url(page=index)) for index in range(page_min, page_max + 1)
    ]

    ctx = {
        "q": q,
        "results": results,
        "results_count": results_count,
        "pagecount": pagecount,
        "filtered_by_type": filtered_by_type,
        "by_object_type": by_object_type,
        "prev_page": prev_page,
        "next_page": next_page,
        "first_page": first_page,
        "last_page": last_page,
        "next_pages_numbered": next_pages_numbered,
        "friendly_fqcn": friendly_fqcn,
    }
    return render_template("search/search.html", **ctx)


class Live(views.JSONView):
    """JSON response for live search."""

    def data(self, q="", page=None, *args, **kwargs):
        if not q:
            q = ""
        svc = get_service("indexing")
        url_for_hit = svc.app_state.url_for_hit
        search_kwargs = {"facet_by_type": True}
        results = svc.search(q, **search_kwargs)
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
