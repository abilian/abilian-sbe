# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals

import re

from abilian.core.models.subjects import User
from flask import g, url_for
from toolz import first

from abilian.sbe.apps.communities.tests.base import CommunityBaseTestCase, \
    CommunityIndexingTestCase
from abilian.sbe.apps.wiki.models import WikiPage


class TestIndexing(CommunityIndexingTestCase):
    def setUp(self):
        super(TestIndexing, self).setUp()
        g.user = User.query.all()[0]

    def test_wiki_indexed(self):
        page = WikiPage(title="Community 1", community=self.community)
        self.session.add(page)

        page_other = WikiPage(title="Community 2: other", community=self.c2)
        self.session.add(page_other)

        self.session.commit()

        svc = self.svc
        obj_types = (WikiPage.entity_type,)
        with self.login(self.user_no_community):
            res = svc.search("community", object_types=obj_types)
            assert len(res) == 0

        with self.login(self.user):
            res = svc.search("community", object_types=obj_types)
            assert len(res) == 1

            hit = res[0]
            assert hit["object_key"] == page.object_key

        with self.login(self.user_c2):
            res = svc.search("community", object_types=obj_types)
            assert len(res) == 1

            hit = res[0]
            assert hit["object_key"] == page_other.object_key


class TestsViews(CommunityBaseTestCase):
    def setUp(self):
        super(TestsViews, self).setUp()
        g.user = User.query.all()[0]

    def test_create_page(self):
        title = "Some page name"
        url = url_for("wiki.page_new", community_id=self.community.slug)
        url += "?title=Some+page+name"
        response = self.client.get(url)
        assert response.status_code == 200
        # make sure the title is filled when comming from wikilink
        assert 'value="Some page name"' in response.get_data(as_text=True)

        title = "Some page"
        body = "LuuP3jai"
        url = url_for("wiki.page_new", community_id=self.community.slug)
        data = {"title": title, "body_src": body, "__action": "create"}
        response = self.client.post(url, data=data)
        assert response.status_code == 302

        url = url_for("wiki.page", community_id=self.community.slug, title=title)
        response = self.client.get(url)
        assert response.status_code == 200
        assert body in response.get_data(as_text=True)

        # edit
        url = url_for("wiki.page_edit", community_id=self.community.slug, title=title)
        response = self.client.get(url)
        assert response.status_code == 200

        # Slightly hackish way to get the page_id
        line = first(
            l
            for l in response.get_data(as_text=True).split("\n")
            if 'name="page_id"' in l
        )
        m = re.search('value="(.*?)"', line)
        page_id = int(m.group(1))

        url = url_for(
            "wiki.page_changes", community_id=self.community.slug, title=title
        )
        response = self.client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_source", community_id=self.community.slug, title=title)
        response = self.client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_edit", community_id=self.community.slug)
        data = {"title": title, "page_id": page_id, "body_src": "abc def"}
        data["__action"] = "edit"
        response = self.client.post(url, data=data)
        assert response.status_code == 302

        url = url_for(
            "wiki.page_compare",
            rev0="on",
            rev1="on",
            community_id=self.community.slug,
            title=title,
        )
        response = self.client.get(url)
        assert response.status_code == 200
