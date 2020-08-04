import re

from flask import g, url_for
from pytest import fixture
from toolz import first

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import READER, Community
from abilian.sbe.apps.wiki import views
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.testing.util import client_login


@fixture
def user1(db):
    user = User(email="user_1@example.com", password="azerty", can_login=True)
    db.session.add(user)
    return user


@fixture
def user2(db):
    user = User(email="user_2@example.com", password="azerty", can_login=True)
    db.session.add(user)
    return user


@fixture
def user3(db):
    user = User(email="user_3@example.com", password="azerty", can_login=True)
    db.session.add(user)
    return user


@fixture
def community1(db, user1):
    community = Community(name="Community 1")
    community.set_membership(user1, READER)
    db.session.add(community)
    return community


@fixture
def community2(db, user2):
    community = Community(name="Community 2")
    community.set_membership(user2, READER)
    db.session.add(community)
    return community


def test_home(client, community1, user1, req_ctx):
    with client_login(client, user1):
        response = client.get(url_for("wiki.index", community_id=community1.slug))
        assert response.status_code == 302

        response = client.get(
            url_for("wiki.page", title="Home", community_id=community1.slug)
        )
        assert response.status_code == 200


def test_create_page_initial_form(client, community1, user1, req_ctx):
    with client:
        with client_login(client, user1):
            g.community = community1
            view = views.PageCreate()
            view.prepare_args([], {})
            form = view.form
            assert form["last_revision_id"].data is None


def test_wiki_indexed(
    community1, community2, admin_user, user1, user2, user3, app, db, client, req_ctx
):
    SERVICES = ("security", "indexing")
    for svc in SERVICES:
        svc = app.services[svc]
        if not svc.running:
            svc.start()

    svc = app.services["indexing"]

    with client:
        with client_login(client, admin_user):
            page1 = WikiPage(title="Community 1", community=community1)
            db.session.add(page1)

            page2 = WikiPage(title="Community 2: other", community=community2)
            db.session.add(page2)

            db.session.commit()

        obj_types = (WikiPage.entity_type,)
        with client_login(client, user3):
            res = svc.search("community", object_types=obj_types)
            assert len(res) == 0

        with client_login(client, user1):
            res = svc.search("community", object_types=obj_types)
            assert len(res) == 1

            hit = res[0]
            assert hit["object_key"] == page1.object_key

        with client_login(client, user2):
            res = svc.search("community", object_types=obj_types)
            assert len(res) == 1

            hit = res[0]
            assert hit["object_key"] == page2.object_key


def test_create_page(community1, app, admin_user, client, req_ctx):
    community = community1

    with client:
        with client_login(client, admin_user):
            url = url_for("wiki.page_new", community_id=community.slug)
            url += "?title=Some+page+name"
            response = client.get(url)
            assert response.status_code == 200
            # make sure the title is filled when comming from wikilink
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
