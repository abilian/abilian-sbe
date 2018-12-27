# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals

import re

from abilian.testing.util import client_login
from flask import g, url_for
from pytest import mark
from toolz import first

from abilian.sbe.apps.wiki import views

pytest_plugins = ["abilian.sbe.apps.communities.tests.fixtures"]


def test_home(client, community1, login_admin):
    response = client.get(url_for("wiki.index", community_id=community1.slug))
    assert response.status_code == 302

    response = client.get(
        url_for("wiki.page", title="Home", community_id=community1.slug)
    )
    assert response.status_code == 200


def test_create_page_initial_form(community1, user, client, req_ctx):
    with client:
        with client_login(client, user):
            g.community = community1
            view = views.PageCreate()
            view.prepare_args([], {})
            form = view.form
            assert form["last_revision_id"].data is None
