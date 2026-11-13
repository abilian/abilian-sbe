# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from flask import current_app, g, session

from abilian.core.application import as_application
from abilian.core.entities import Entity

# Not used in UI, currently.


def add_to_recent_items(entity, type="ignored") -> None:
    if not isinstance(entity, Entity):
        return
    object_type = entity.object_type
    url = as_application(current_app).default_view.url_for(entity)
    if not hasattr(g, "recent_items"):
        g.recent_items = []
    g.recent_items.insert(0, {"type": object_type, "name": entity.name, "url": url})

    s = set()
    new_recent_items = []
    for item in g.recent_items:
        item_url = item["url"]
        if item_url in s:
            continue
        s.add(item_url)
        new_recent_items.append(item)
    if len(new_recent_items) > 5:
        del new_recent_items[5:]
    session["recent_items"] = g.recent_items = new_recent_items
