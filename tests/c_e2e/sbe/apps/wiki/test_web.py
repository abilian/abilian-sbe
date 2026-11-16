# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from flask import g, url_for
from pytest import fixture
from toolz import first

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import READER, Community
from abilian.sbe.apps.wiki import views
from abilian.sbe.apps.wiki.models import WikiPage, WikiPageAttachment
from abilian.services import get_service, security_service
from abilian.services.security import ADMIN
from tests.util import client_login

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy

    from abilian.app import Application


@fixture
def user1(db):
    user = User(
        email="user_1@example.com",
        password="azerty",  # noqa: S106
        can_login=True,
    )
    db.session.add(user)
    return user


@fixture
def user2(db):
    user = User(
        email="user_2@example.com",
        password="azerty",  # noqa: S106
        can_login=True,
    )
    db.session.add(user)
    return user


@fixture
def user3(db):
    user = User(
        email="user_3@example.com",
        password="azerty",  # noqa: S106
        can_login=True,
    )
    db.session.add(user)
    return user


@fixture
def community1(db, user1):
    community = Community(name="Community 1")
    db.session.add(community)
    community.set_membership(user1, READER)
    return community


@fixture
def community2(db, user2):
    community = Community(name="Community 2")
    db.session.add(community)
    community.set_membership(user2, READER)
    return community


def test_home(client, community1, user1) -> None:
    with client_login(client, user1):
        response = client.get(url_for("wiki.index", community_id=community1.slug))
        assert response.status_code == 302

        response = client.get(
            url_for("wiki.page", title="Home", community_id=community1.slug)
        )
        assert response.status_code == 200


def test_create_page_initial_form(client, community1, user1) -> None:
    with client_login(client, user1):
        g.community = community1
        view = views.PageCreate()
        view.prepare_args([], {})
        form = view.form
        assert form["last_revision_id"].data is None


def test_wiki_indexed(
    community1,
    community2,
    admin_user,
    user1,
    user2,
    user3,
    app: Application,
    db: SQLAlchemy,
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    SERVICES = ("security", "indexing")
    for svc_name in SERVICES:
        svc = get_service(svc_name)
        if not svc.running:
            svc.start()

    get_service("indexing")

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


def test_create_page(community1, app, admin_user, client) -> None:
    community = community1

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
        m = re.search(r'value="(.*?)"', line)
        page_id = int(m.group(1))

        url = url_for("wiki.page_changes", community_id=community.slug, title=title)
        response = client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_source", community_id=community.slug, title=title)
        response = client.get(url)
        assert response.status_code == 200

        url = url_for("wiki.page_edit", community_id=community.slug)
        data = {
            "title": title,
            "page_id": page_id,
            "body_src": "abc def",
            "__action": "edit",
        }
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


@pytest.mark.parametrize(
    ("endpoint", "method"),
    [("wiki.attachment_download", "get"), ("wiki.attachment_delete", "post")],
)
def test_an_attachment_of_another_page_is_not_found(
    app, db, client, community1, user1, endpoint, method
) -> None:
    security_service.start()
    security_service.grant_role(user1, ADMIN)
    with client_login(client, user1):
        page = WikiPage(title="Here", body_src="here", community=community1)
        other = WikiPage(title="There", body_src="there", community=community1)
        attachment = WikiPageAttachment(name="secret.txt")
        attachment.set_content(b"secret", "text/plain")
        other.attachments.append(attachment)
        db.session.add_all([page, other])
        db.session.commit()

        for attachment_id in (attachment.id, 999999):
            url = url_for(
                endpoint,
                community_id=community1.slug,
                title="Here",
                attachment=attachment_id,
            )
            assert getattr(client, method)(url).status_code == 404, attachment_id

        # The test cleanup cannot drop the tables while a wiki attachment is
        # left: a foreign key it does not untangle (to be found).
        db.session.delete(attachment)
        db.session.commit()
