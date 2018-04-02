# -*- coding: utf-8 -*-
"""Document management blueprint."""
from __future__ import absolute_import, print_function, unicode_literals

from abilian.i18n import _l
from abilian.web.action import Endpoint
from abilian.web.nav import BreadcrumbItem
from flask import g

from abilian.sbe.apps.communities.blueprint import Blueprint
from abilian.sbe.apps.communities.security import is_manager

from ..actions import register_actions

__all__ = ['blueprint']

blueprint = Blueprint(
    "documents",
    __name__,
    url_prefix="/docs",
    template_folder="../templates",
)
route = blueprint.route
blueprint.record_once(register_actions)


@blueprint.url_value_preprocessor
def init_document_values(endpoint, values):
    g.current_tab = 'documents'
    g.is_manager = is_manager()

    g.breadcrumb.append(
        BreadcrumbItem(
            label=_l('Documents'),
            url=Endpoint('documents.index', community_id=g.community.slug),
        ),
    )
