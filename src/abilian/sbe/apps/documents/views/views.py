# Copyright (c) 2012-2024, Abilian SAS

"""Document management blueprint."""

from __future__ import annotations

from flask import g

from abilian.i18n import _l
from abilian.sbe.apps.communities.blueprint import CommunityBlueprint
from abilian.sbe.apps.documents.actions import register_actions
from abilian.web.action import Endpoint
from abilian.web.nav import BreadcrumbItem

__all__ = ["community_blueprint"]

community_blueprint = CommunityBlueprint(
    "documents", __name__, url_prefix="/docs", template_folder="../templates"
)
route = community_blueprint.route
community_blueprint.record_once(register_actions)


@community_blueprint.url_value_preprocessor
def init_document_values(endpoint: str, values: dict[str, int]) -> None:
    g.current_tab = "documents"

    g.breadcrumb.append(
        BreadcrumbItem(
            label=_l("Documents"),
            url=Endpoint("documents.index", community_id=g.community.slug),
        )
    )
