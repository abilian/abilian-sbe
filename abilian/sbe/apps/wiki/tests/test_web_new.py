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


def test_create_page_initial_form(community1, user, req_ctx):
    g.user = user
    g.community = community1
    view = views.PageCreate()
    view.prepare_args([], {})
    form = view.form
    assert form["last_revision_id"].data is None


@mark.skip  # TODO: fixme later
def test_create_page(client, community1, req_ctx):
    community = community1
    user = community.test_user

    with client_login(client, user):
        title = "Some page name"
        url = url_for("wiki.page_new", community_id=community.slug)
        url += "?title=Some+page+name"
        response = client.get(url)
        assert response.status_code == 200
        # make sure the title is filled when coming from wikilink
        assert 'value="Some page name"' in response.get_data(as_text=True)

        title = "Some page"
        body = "LuuP3jai"
        url = url_for("wiki.page_new", community_id=community.slug)
        data = {"title": title, "body_src": body, "__action": "create"}
        response = client.post(url, data=data)
        assert response.status_code == 302

        url = url_for("wiki.page", community_id=community.slug, title=title)
        response = client.get(url)
        assert response.status_code == 200
        assert body in response.get_data(as_text=True)

        # edit
        url = url_for("wiki.page_edit", community_id=community.slug, title=title)
        response = client.get(url)
        assert response.status_code == 200

        # Slightly hackish way to get the page_id
        line = first(
            l
            for l in response.get_data(as_text=True).split("\n")
            if 'name="page_id"' in l
        )
        m = re.search('value="(.*?)"', line)
        page_id = int(m.group(1))

        url = url_for("wiki.page_changes", community_id=community.slug, title=title)
        response = client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_source", community_id=community.slug, title=title)
        response = client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_edit", community_id=community.slug)
        data = {"title": title, "page_id": page_id, "body_src": "abc def"}
        data["__action"] = "edit"
        response = client.post(url, data=data)
        assert response.status_code == 302

        url = url_for(
            "wiki.page_compare",
            rev0="on",
            rev1="on",
            community_id=community.slug,
            title=title,
        )
        response = client.get(url)
        assert response.status_code == 200
