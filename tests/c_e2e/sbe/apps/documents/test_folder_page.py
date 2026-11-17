# Copyright (c) 2012-2026, Abilian SAS

"""A folder's page on the Abilian Design System: the tree beside it, its two views,
and what is offered to whom.

The table's filter, sort and pages are in `tests/c_e2e/sbe/apps/communities/
test_listings.py`; what the scripts do with it, in `e2e_playwright/`.
"""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.documents.views.folders import folder_tree
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community
    from abilian.sbe.apps.documents.models import Folder

UPLOAD = 'data-modal-open="#modal-upload-files"'
DELETE_ROW = 'data-row-action="delete"'


@pytest.fixture
def folders(community1: Community, db: SQLAlchemy) -> tuple[Folder, Folder, Folder]:
    """The community's folder, holding "Minutes" and "Reports", which holds "2026"."""
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MANAGER)
    root = community1.folder
    reports = root.create_subfolder("Reports")
    year = reports.create_subfolder("2026")
    root.create_subfolder("Minutes")
    budget = year.create_document(title="budget.pdf")
    budget.set_content(b"%PDF-1.4", "application/pdf")
    db.session.commit()
    return root, reports, year


def _member(db: SQLAlchemy, community: Community, role) -> User:
    user = User(
        email=f"{uuid4().hex}@example.com", password=uuid4().hex, can_login=True
    )
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.commit()
    return user


def _page(client: FlaskClient, user: User, folder: Folder) -> str:
    with client_login(client, user):
        response = client.get(url_for(folder))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def test_the_tree_is_open_down_to_the_folder_shown(
    folders: tuple[Folder, Folder, Folder], community1: Community
) -> None:
    root, _, year = folders

    (top,) = folder_tree(root, community1.test_user, year)

    assert top.expanded
    assert not top.current
    by_title = {node.folder.title: node for node in top.children}
    assert by_title.keys() == {"Minutes", "Reports"}
    assert by_title["Reports"].expanded
    assert not by_title["Minutes"].expanded
    (shown,) = by_title["Reports"].children
    assert shown.folder is year
    assert shown.current


def test_the_page_shows_the_tree_and_what_a_folder_holds(
    folders: tuple[Folder, Folder, Folder], client: FlaskClient, community1: Community
) -> None:
    root, _, year = folders

    html = _page(client, community1.test_user, root)

    assert f'href="{url_for(year)}" aria-current="page"' not in html
    assert f'href="{url_for(root)}" aria-current="page"' in html
    row = html.split('aria-label="Select Reports"')[1].split("</tr>")[0]
    assert "1 item" in row


def test_a_reader_is_offered_nothing_that_writes(
    folders: tuple[Folder, Folder, Folder],
    client: FlaskClient,
    community1: Community,
    db: SQLAlchemy,
) -> None:
    root, _, _ = folders
    # The members of a community that is not participative read its documents.
    reader = _member(db, community1, MEMBER)

    html = _page(client, reader, root)

    assert "Reports" in html
    assert UPLOAD not in html
    assert DELETE_ROW not in html
    assert 'id="modal-upload-files"' not in html
    assert 'id="modal-change-owner"' not in html


def test_a_member_of_a_participative_community_writes_but_does_not_change_owners(
    folders: tuple[Folder, Folder, Folder],
    client: FlaskClient,
    community1: Community,
    db: SQLAlchemy,
) -> None:
    root, _, _ = folders
    community1.type = "participative"
    writer = _member(db, community1, MEMBER)
    community1.update_roles_on_folder()
    db.session.commit()

    html = _page(client, writer, root)

    assert UPLOAD in html
    assert DELETE_ROW in html
    assert 'data-modal-open="#modal-change-owner"' not in html


def test_the_gallery_shows_the_same_items_as_tiles(
    folders: tuple[Folder, Folder, Folder], client: FlaskClient, community1: Community
) -> None:
    _, _, year = folders
    with client.session_transaction() as session:
        session["sbe_doc_view_style"] = "gallery_view"

    html = _page(client, community1.test_user, year)

    assert 'id="objects-table"' not in html
    tiles = html.split('class="ads-grid sbe-gallery"')[1].split("</ul>")[0]
    assert "budget.pdf" in tiles
    assert 'name="object-selected"' in tiles
    assert 'value="gallery_view" aria-pressed="true"' in html
