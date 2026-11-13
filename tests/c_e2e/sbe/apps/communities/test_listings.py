# Copyright (c) 2012-2024, Abilian SAS

"""The tables are server-rendered: what a page contains is what the server sent.

Each table is checked through its URL, the way a link or a bookmark reaches it.
abilian/web/listing.py has the fine print on sorting and paging; this is about
each table wiring its own columns to it.
"""

from __future__ import annotations

import datetime as dt
import re
from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from flask import url_for

from abilian.core.models.subjects import Group, User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.services import security_service
from abilian.services.security import READER
from abilian.web.listing import PER_PAGE
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _person(db: SQLAlchemy, first: str, last: str, **kw) -> User:
    user = User(
        first_name=first,
        last_name=last,
        email=f"{first}.{last}@example.com".lower(),
        password=uuid4().hex,
        can_login=True,
        **kw,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _get(client: FlaskClient, viewer: User, url: str) -> str:
    with client_login(client, viewer):
        response = client.get(url)
    assert response.status_code == 200, url
    return unescape(response.get_data(as_text=True))


def _body(html: str) -> str:
    """The rows of the first table, so names elsewhere on the page don't count."""
    match = re.search(r"<tbody.*?</tbody>", html, re.DOTALL)
    assert match, "no table on the page"
    return match.group(0)


def _in_order(html: str, *names: str) -> bool:
    """These names appear in the rows, in this order."""
    body = _body(html)
    positions = [body.find(name) for name in names]
    return -1 not in positions and positions == sorted(positions)


# The admin panels and the directory: filtered and sorted by the database.


@pytest.fixture
def people(db: SQLAlchemy) -> dict[str, User]:
    ann = _person(db, "Ann", "Young", last_active=dt.datetime(2020, 1, 1))
    bob = _person(db, "Bob", "Xavier", last_active=dt.datetime(2024, 1, 1))
    cid = _person(db, "Cid", "Zorn")
    db.session.commit()
    return {"ann": ann, "bob": bob, "cid": cid}


@pytest.mark.parametrize("endpoint", ["admin.users", "social.users"])
def test_people_are_listed_by_last_name(
    endpoint: str, client: FlaskClient, admin_user: User, people: dict[str, User]
) -> None:
    html = _get(client, admin_user, url_for(endpoint))
    assert _in_order(html, "Bob Xavier", "Ann Young", "Cid Zorn")


@pytest.mark.parametrize("endpoint", ["admin.users", "social.users"])
def test_people_are_filtered_by_name(
    endpoint: str, client: FlaskClient, admin_user: User, people: dict[str, User]
) -> None:
    html = _get(client, admin_user, url_for(endpoint, q="YOU"))
    assert "Ann Young" in _body(html)
    assert "Bob Xavier" not in _body(html)
    # The field still says what was asked for.
    assert 'name="q" value="YOU"' in html


def test_the_filter_wildcards_are_not_wildcards(
    client: FlaskClient, admin_user: User, people: dict[str, User]
) -> None:
    html = _get(client, admin_user, url_for("admin.users", q="%"))
    assert "Ann Young" not in _body(html)
    assert "No matching records found" in _body(html)


def test_the_admin_table_filters_by_email_too(
    client: FlaskClient, admin_user: User, people: dict[str, User]
) -> None:
    html = _get(client, admin_user, url_for("admin.users", q="bob.xavier@"))
    assert "Bob Xavier" in _body(html)
    assert "Ann Young" not in _body(html)


def test_the_directory_does_not_filter_by_email(
    client: FlaskClient, admin_user: User, people: dict[str, User]
) -> None:
    """People may search each other by name; addresses are not theirs to mine."""
    html = _get(client, admin_user, url_for("social.users", q="bob.xavier@"))
    assert "Bob Xavier" not in _body(html)


@pytest.mark.parametrize(
    ("endpoint", "sort"),
    [("admin.users", "last_active"), ("social.users", "last_active")],
)
def test_people_who_never_came_sort_last_both_ways(
    endpoint: str,
    sort: str,
    client: FlaskClient,
    admin_user: User,
    people: dict[str, User],
) -> None:
    ascending = _get(client, admin_user, url_for(endpoint, sort=sort))
    assert _in_order(ascending, "Ann Young", "Bob Xavier", "Cid Zorn")

    descending = _get(client, admin_user, url_for(endpoint, sort=f"-{sort}"))
    assert _in_order(descending, "Bob Xavier", "Ann Young", "Cid Zorn")


def test_people_with_the_same_name_keep_one_order_across_pages(
    db: SQLAlchemy, client: FlaskClient, admin_user: User
) -> None:
    """Each page is its own query, so a tie the database may break differently
    each time can show a row on two pages, or on none."""
    for email in ("first.twin@example.com", "second.twin@example.com"):
        db.session.add(
            User(
                first_name="Sam",
                last_name="Twin",
                email=email,
                password=uuid4().hex,
                can_login=True,
            )
        )
    db.session.flush()

    ascending = _get(client, admin_user, url_for("admin.users", q="twin", sort="name"))
    assert _in_order(ascending, "first.twin@example.com", "second.twin@example.com")

    descending = _get(
        client, admin_user, url_for("admin.users", q="twin", sort="-name")
    )
    assert _in_order(descending, "second.twin@example.com", "first.twin@example.com")


def test_the_admin_table_sorts_by_email(
    client: FlaskClient, admin_user: User, people: dict[str, User]
) -> None:
    html = _get(client, admin_user, url_for("admin.users", sort="-email"))
    assert _in_order(html, "Cid Zorn", "Bob Xavier", "Ann Young")


def test_the_directory_sorts_by_registration(
    client: FlaskClient, admin_user: User, people: dict[str, User], db: SQLAlchemy
) -> None:
    people["cid"].created_at = dt.datetime(2001, 1, 1)
    people["ann"].created_at = dt.datetime(2002, 1, 1)
    people["bob"].created_at = dt.datetime(2003, 1, 1)
    db.session.commit()

    html = _get(client, admin_user, url_for("social.users", sort="created_at"))
    assert _in_order(html, "Cid Zorn", "Ann Young", "Bob Xavier")


def test_a_name_is_escaped(
    client: FlaskClient, admin_user: User, db: SQLAlchemy
) -> None:
    """The cells used to be HTML built by hand and handed over as JSON."""
    _person(db, "<script>x</script>", "Bad")
    db.session.commit()

    for endpoint in ("admin.users", "social.users"):
        with client_login(client, admin_user):
            raw = client.get(url_for(endpoint)).get_data(as_text=True)
        assert "<script>x</script>" not in raw


def test_the_admin_table_lists_groups_and_login_state(
    client: FlaskClient, admin_user: User, people: dict[str, User], db: SQLAlchemy
) -> None:
    group = Group(name="The Testers")
    db.session.add(group)
    db.session.flush()
    people["ann"].groups.add(group)
    db.session.commit()

    html = _get(client, admin_user, url_for("admin.users", q="young"))
    assert "The Testers" in _body(html)
    assert url_for("admin.users_user", user_id=people["ann"].id) in _body(html)
    assert "✓" in _body(html)


def test_people_are_paged(
    client: FlaskClient, admin_user: User, db: SQLAlchemy
) -> None:
    for number in range(PER_PAGE + 1):
        _person(db, "Paged", f"Person{number:03}")
    db.session.commit()

    first = _get(client, admin_user, url_for("admin.users", q="person"))
    assert "Person000" in _body(first)
    assert f"Person{PER_PAGE:03}" not in _body(first)
    assert 'aria-current="page"' in first
    assert "?q=person&page=2" in first

    second = _get(client, admin_user, url_for("admin.users", q="person", page=2))
    assert f"Person{PER_PAGE:03}" in _body(second)
    assert "Person000" not in _body(second)


def test_groups_are_listed_filtered_and_sorted(
    client: FlaskClient, admin_user: User, db: SQLAlchemy
) -> None:
    alpha, beta = Group(name="Alpha"), Group(name="beta")
    db.session.add_all([alpha, beta])
    admin_user.groups.add(alpha)
    db.session.commit()

    html = _get(client, admin_user, url_for("admin.groups"))
    assert _in_order(html, "Alpha", "beta")
    assert url_for("admin.groups_group", group_id=alpha.id) in _body(html)

    html = _get(client, admin_user, url_for("admin.groups", sort="-name"))
    assert _in_order(html, "beta", "Alpha")

    html = _get(client, admin_user, url_for("admin.groups", q="BET"))
    assert "beta" in _body(html)
    assert "Alpha" not in _body(html)


@pytest.mark.parametrize("endpoint", ["admin.users", "admin.groups"])
def test_the_admin_tables_refuse_a_plain_user(
    endpoint: str, client: FlaskClient, user: User, db_session
) -> None:
    with client_login(client, user):
        assert client.get(url_for(endpoint)).status_code == 403


# Members: every row is computed by the view, and is sorted and cut in Python.


@pytest.fixture
def members(community1: Community, db: SQLAlchemy) -> dict[str, User]:
    ensure_services_started(["security"])
    ann = _person(db, "Ann", "Young")
    bob = _person(db, "Bob", "Xavier")
    community1.set_membership(ann, MANAGER)
    community1.set_membership(bob, MEMBER)
    db.session.commit()
    return {"ann": ann, "bob": bob}


def _members_url(community: Community, **args: str) -> str:
    return url_for("communities.members", community_id=community.slug, **args)


def test_members_are_listed_by_last_name(
    client: FlaskClient, community1: Community, members: dict[str, User]
) -> None:
    html = _get(client, members["ann"], _members_url(community1))
    assert _in_order(html, "Bob Xavier", "Ann Young")
    html = _get(client, members["ann"], _members_url(community1, sort="-name"))
    assert _in_order(html, "Ann Young", "Bob Xavier")


def test_members_are_filtered_by_name_and_email(
    client: FlaskClient, community1: Community, members: dict[str, User]
) -> None:
    for query in ("young", "ann.young@"):
        html = _get(client, members["ann"], _members_url(community1, q=query))
        assert "Ann Young" in _body(html)
        assert "Bob Xavier" not in _body(html)


@pytest.mark.parametrize("sort", ["posts", "activity", "role"])
def test_members_sort_by_every_column(
    sort: str, client: FlaskClient, community1: Community, members: dict[str, User]
) -> None:
    """Members with no activity have no date, which must not break the sort."""
    html = _get(client, members["ann"], _members_url(community1, sort=sort))
    assert "Ann Young" in _body(html)
    assert "Bob Xavier" in _body(html)


def test_members_sort_by_role(
    client: FlaskClient, community1: Community, members: dict[str, User]
) -> None:
    html = _get(client, members["ann"], _members_url(community1, sort="role"))
    assert _in_order(html, "Ann Young", "Bob Xavier")


def test_managing_a_member_works_from_a_filtered_page(
    client: FlaskClient, community1: Community, members: dict[str, User]
) -> None:
    """The role and delete forms are in the rows, the filter is not around them."""
    html = _get(client, members["ann"], _members_url(community1, q="xavier"))
    assert 'name="action" value="set-user-role"' in _body(html)
    # A form cannot sit inside another: the filter closes before the table opens.
    assert html.index('role="search"') < html.index("</form>") < html.index("<tbody")


# Folder permissions: two tables on one page.


@pytest.fixture
def folder_with_roles(community1: Community, db: SQLAlchemy):
    ensure_services_started(["security"])
    folder = community1.folder.create_subfolder("Restricted")
    db.session.flush()
    ann = _person(db, "Ann", "Young")
    bob = _person(db, "Bob", "Xavier")
    community1.set_membership(ann, MANAGER)
    return folder, ann, bob


def _permissions_url(folder, **args: str) -> str:
    return url_for(
        "documents.permissions",
        community_id=folder.community.slug,
        folder_id=folder.id,
        **args,
    )


def test_the_two_permission_tables_keep_their_own_filter(
    client: FlaskClient, folder_with_roles, db: SQLAlchemy
) -> None:
    folder, ann, bob = folder_with_roles
    # Logged in, as through the real form: the audit log names who did it.
    with client_login(client, ann):
        client.get(_permissions_url(folder))
        security_service.grant_role(ann, READER, folder)
        security_service.grant_role(bob, READER, folder)
        db.session.commit()

    html = _get(client, ann, _permissions_url(folder))
    assert _in_order(html, "Bob Xavier", "Ann Young")

    html = _get(client, ann, _permissions_url(folder, local_q="young"))
    assert "Ann Young" in _body(html)
    assert "Bob Xavier" not in _body(html)

    # The other table's filter leaves this one alone.
    html = _get(client, ann, _permissions_url(folder, inherited_q="young"))
    assert _in_order(html, "Bob Xavier", "Ann Young")

    html = _get(client, ann, _permissions_url(folder, local_sort="-name"))
    assert _in_order(html, "Ann Young", "Bob Xavier")


# The folder listing.


@pytest.fixture
def folder_content(community1: Community, db: SQLAlchemy):
    ensure_services_started(["security"])
    owner = community1.test_user
    community1.set_membership(owner, MANAGER)
    folder = community1.folder

    subfolder = folder.create_subfolder("Zebra folder")
    small = folder.create_document(title="alpha.txt")
    small.set_content(b"x", "text/plain")
    big = folder.create_document(title="Beta.txt")
    big.set_content(b"x" * 5000, "text/plain")

    subfolder.created_at = dt.datetime(2020, 1, 1)
    small.created_at = dt.datetime(2021, 1, 1)
    big.created_at = dt.datetime(2022, 1, 1)
    for content in (subfolder, small, big):
        content.owner = content.creator = owner
    db.session.commit()
    return folder, owner


def _folder_url(folder, **args: str) -> str:
    return url_for(
        "documents.folder_view",
        community_id=folder.community.slug,
        folder_id=folder.id,
        **args,
    )


def test_folders_come_first_then_documents_by_title(
    client: FlaskClient, folder_content
) -> None:
    folder, owner = folder_content
    html = _get(client, owner, _folder_url(folder))
    assert _in_order(html, "Zebra folder", "alpha.txt", "Beta.txt")


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("-title", ("Beta.txt", "alpha.txt", "Zebra folder")),
        ("size", ("Zebra folder", "alpha.txt", "Beta.txt")),
        ("-size", ("Beta.txt", "alpha.txt", "Zebra folder")),
        # The youngest first: it is the age going up.
        ("age", ("Beta.txt", "alpha.txt", "Zebra folder")),
        ("-age", ("Zebra folder", "alpha.txt", "Beta.txt")),
    ],
)
def test_the_folder_listing_sorts(
    sort: str, expected: tuple[str, ...], client: FlaskClient, folder_content
) -> None:
    folder, owner = folder_content
    html = _get(client, owner, _folder_url(folder, sort=sort))
    assert _in_order(html, *expected)


def test_the_folder_listing_sorts_by_owner(client: FlaskClient, folder_content) -> None:
    folder, owner = folder_content
    html = _get(client, owner, _folder_url(folder, sort="owner"))
    assert "alpha.txt" in _body(html)


def test_the_folder_listing_filters_by_title(
    client: FlaskClient, folder_content
) -> None:
    folder, owner = folder_content
    html = _get(client, owner, _folder_url(folder, q="BETA"))
    assert "Beta.txt" in _body(html)
    assert "alpha.txt" not in _body(html)
    assert "Zebra folder" not in _body(html)


def test_a_filter_matching_nothing_is_not_an_empty_folder(
    client: FlaskClient, folder_content
) -> None:
    """Otherwise the filter box goes, and there is no way back but the URL."""
    folder, owner = folder_content
    html = _get(client, owner, _folder_url(folder, q="no such file"))
    assert "No matching records found" in html
    assert "currently empty" not in html
    assert 'value="no such file"' in html


def test_an_empty_folder_says_so(
    client: FlaskClient, community1: Community, db: SQLAlchemy
) -> None:
    ensure_services_started(["security"])
    owner = community1.test_user
    community1.set_membership(owner, MANAGER)
    db.session.commit()

    html = _get(client, owner, _folder_url(community1.folder))
    assert "currently empty" in html
