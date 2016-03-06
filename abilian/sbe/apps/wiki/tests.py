# coding=utf-8
from __future__ import absolute_import

import re
from urllib import quote_plus

from flask import g, url_for
from markdown import Markdown
from mock import MagicMock, patch

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.tests.base import (CommunityBaseTestCase,
                                                     CommunityIndexingTestCase)
from abilian.sbe.apps.wiki.markup import SBEWikiLinkExtension

from . import views
from .models import WikiPage


def test_wikilink_extension():
    text = u'/*€('
    wikilink = u'[[' + text + ']]'

    def build_url(label, base, end):
        return u'/?title=' + quote_plus(label.encode('utf-8')) + end

    extension = SBEWikiLinkExtension([('build_url', build_url)])
    ctx = {}
    ctx['extensions'] = [extension, 'toc']
    ctx['output_format'] = 'html5'
    md = Markdown(**ctx)

    page_exists_mock = MagicMock(return_value=True)
    with patch('abilian.sbe.apps.wiki.forms.page_exists', page_exists_mock):
        result = md.convert(wikilink)

    qtext = unicode(quote_plus(text.encode('utf-8')))
    expected = u'<p><a class="wikilink" href="/?title={href}/">{text}</a></p>'
    expected = expected.format(href=qtext, text=text)
    assert expected == result

    # make sur the class is 'wikilink new' if page exists'
    page_exists_mock = MagicMock(return_value=False)
    with patch('abilian.sbe.apps.wiki.forms.page_exists', page_exists_mock):
        result = md.convert(wikilink)

    qtext = unicode(quote_plus(text.encode('utf-8')))
    expected = u'<p><a class="wikilink new" href="/?title={href}/">{text}</a></p>'
    expected = expected.format(href=qtext, text=text)
    assert expected == result


class WikiBaseTestCase(CommunityBaseTestCase):

    def setUp(self):
        super(WikiBaseTestCase, self).setUp()
        g.user = User.query.all()[0]


class TestModels(WikiBaseTestCase):

    def test_create_page(self):
        page = WikiPage(title=u"Some page", body_src=u'abc')
        self.assertEquals(page.title, u'Some page')
        self.assertEquals(page.name, u'Some page')
        self.assertEquals(page.body_src, 'abc')
        self.assertEquals(page.body_html, '<p>abc</p>')
        self.assertEquals(len(page.revisions), 1)

        revision = page.revisions[0]
        self.assertEquals(revision.number, 0)
        self.assertEquals(revision.author, g.user)

    def test_rename_page(self):
        page = WikiPage(title=u"Some page", body_src=u'abc')
        self.assertEquals(page.title, u'Some page')
        self.assertEquals(page.name, u'Some page')
        page.title = u'Title Renamed'
        self.assertEquals(page.title, u'Title Renamed')
        self.assertEquals(page.name, u'Title Renamed')

        page.name = u'Name'
        self.assertEquals(page.title, u'Name')
        self.assertEquals(page.name, u'Name')

    def test_create_revision(self):
        page = WikiPage('abc')
        page.create_revision("def", "page updated")

        self.assertEquals(len(page.revisions), 2)
        last_revision = page.revisions[1]
        self.assertEquals(last_revision.number, 1)
        self.assertEquals(last_revision.author, g.user)


class TestIndexing(CommunityIndexingTestCase):

    def setUp(self):
        super(TestIndexing, self).setUp()
        g.user = User.query.all()[0]

    def test_wiki_indexed(self):
        page = WikiPage(title=u'Community 1', community=self.community)
        self.session.add(page)
        page_other = WikiPage(title=u'Community 2: other', community=self.c2)
        self.session.add(page_other)
        self.session.commit()

        svc = self.svc
        obj_types = (WikiPage.entity_type,)
        with self.login(self.user_no_community):
            res = svc.search(u'community', object_types=obj_types)
            self.assertEquals(len(res), 0)

        with self.login(self.user):
            res = svc.search(u'community', object_types=obj_types)
            self.assertEquals(len(res), 1)
            hit = res[0]
            self.assertEquals(hit['object_key'], page.object_key)

        with self.login(self.user_c2):
            res = svc.search(u'community', object_types=obj_types)
            self.assertEquals(len(res), 1)
            hit = res[0]
            self.assertEquals(hit['object_key'], page_other.object_key)


class TestsViews(WikiBaseTestCase):

    def test_home(self):
        response = self.client.get(url_for("wiki.index",
                                           community_id=self.community.slug))
        self.assertStatus(response, 302)

        response = self.client.get(url_for("wiki.page",
                                           title='Home',
                                           community_id=self.community.slug))
        assert response.status_code == 200

    def test_create_page_initial_form(self):
        g.community = self.community
        view = views.PageCreate()
        view.prepare_args([], {})
        form = view.form
        assert form['last_revision_id'].data is None

    def test_create_page(self):
        title = 'Some page name'
        url = url_for("wiki.page_new", community_id=self.community.slug)
        url += '?title=Some+page+name'
        response = self.client.get(url)
        assert response.status_code == 200
        # make sure the title is filled when comming from wikilink
        self.assertIn('value="Some page name"', response.data)

        title = 'Some page'
        body = "LuuP3jai"
        url = url_for("wiki.page_new", community_id=self.community.slug)
        data = dict(title=title, body_src=body, __action="create")
        response = self.client.post(url, data=data)
        assert response.status_code == 302

        url = url_for("wiki.page",
                      community_id=self.community.slug,
                      title=title)
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertIn(body, response.data)

        # edit
        url = url_for("wiki.page_edit",
                      community_id=self.community.slug,
                      title=title)
        response = self.client.get(url)
        assert response.status_code == 200

        # Slightly hackish way to get the page_id
        line = [l for l in response.data.split("\n")
                if 'name="page_id"' in l][0]
        m = re.search('value="(.*?)"', line)
        page_id = int(m.group(1))

        url = url_for("wiki.page_changes",
                      community_id=self.community.slug,
                      title=title)
        response = self.client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_source",
                      community_id=self.community.slug,
                      title=title)
        response = self.client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_edit", community_id=self.community.slug)
        data = dict(title=title, page_id=page_id, body_src="abc def")
        data['__action'] = 'edit'
        response = self.client.post(url, data=data)
        assert response.status_code == 302

        url = url_for("wiki.page_compare",
                      rev0="on",
                      rev1="on",
                      community_id=self.community.slug,
                      title=title)
        response = self.client.get(url)
        assert response.status_code == 200
