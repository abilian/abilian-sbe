# -*- coding: utf-8 -*-
"""
Document management blueprint.
"""
from __future__ import absolute_import

from flask import g
from flask.ext.babel import gettext as _
from abilian.web import nav
from abilian.sbe.apps.communities.blueprint import Blueprint

from ..actions import register_actions

__all__ = ['documents']


documents = Blueprint("documents", __name__,
                      url_prefix="/docs",
                      template_folder="../templates")
route = documents.route
documents.record_once(register_actions)


@documents.url_value_preprocessor
def init_document_values(endpoint, values):
  g.current_tab = 'documents'

  g.breadcrumb.append(
    nav.BreadcrumbItem(label=_(u'Documents'),
                       url=nav.Endpoint('documents.index',
                                        community_id=g.community.slug)))
