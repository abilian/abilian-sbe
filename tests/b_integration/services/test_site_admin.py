# Copyright (c) 2012-2024, Abilian SAS

"""`is_site_admin`, and the search bypass that used to be decided twice.

Both questions were answered by reading `g.is_manager`, an attribute two
producers wrote with two different meanings -- site-wide from AuthService, and
community-scoped from the documents blueprint, which overwrote it. Neither
reader could tell which one it had.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import whoosh.query as wq
from flask import render_template_string

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.search import filter_user_communities
from abilian.services import security_service
from abilian.services.security import ADMIN, MANAGER, is_site_admin
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


@pytest.fixture
def plain_user(db: SQLAlchemy) -> User:
    user = User(email="plain@example.com", can_login=True)
    db.session.add(user)
    db.session.flush()
    return user


def test_a_plain_user_is_not_a_site_admin(plain_user: User, app: Application) -> None:
    ensure_services_started(["security"])

    assert not is_site_admin(plain_user)


def test_an_admin_is(plain_user: User, db: SQLAlchemy, app: Application) -> None:
    ensure_services_started(["security"])
    security_service.grant_role(plain_user, ADMIN)
    db.session.flush()

    assert is_site_admin(plain_user)


def test_a_site_manager_is_too(
    plain_user: User, db: SQLAlchemy, app: Application
) -> None:
    """`has_role` seeds valid_roles with {ADMIN, MANAGER}, so a site manager
    answers True to any role. AuthService asked both and got one answer twice."""
    ensure_services_started(["security"])
    security_service.grant_role(plain_user, MANAGER)
    db.session.flush()

    assert is_site_admin(plain_user)


def test_an_anonymous_visitor_is_not(app: Application) -> None:
    ensure_services_started(["security"])

    with app.test_request_context("/"):
        assert not is_site_admin()


def test_a_community_manager_is_not_a_site_admin(
    community1: Community, plain_user: User, db: SQLAlchemy, app: Application
) -> None:
    """The confusion the two producers created, stated as an assertion.

    Managing one community said nothing about the site, but inside the
    documents blueprint `g.is_manager` carried the community answer to readers
    asking the site question -- including the one that decides whether to apply
    the site-wide search filter at all.
    """
    ensure_services_started(["security"])
    community1.set_membership(plain_user, MANAGER)
    db.session.flush()

    assert not is_site_admin(plain_user)


def test_the_community_filter_narrows_to_the_user_s_communities(
    community1: Community, plain_user: User, db: SQLAlchemy, app: Application
) -> None:
    ensure_services_started(["security"])
    community1.set_membership(plain_user, MANAGER)
    db.session.flush()

    query = filter_user_communities(plain_user)

    # "not community content" OR ("community content" AND one of mine)
    assert isinstance(query, wq.Or)
    assert wq.Term("community_id", community1.id) in list(query.leaves())


def test_the_filter_needs_no_request(plain_user: User, app: Application) -> None:
    """It read `current_user` and `g.is_manager` before, so it could not run
    outside a request -- which a dramatiq task or the CLI is."""
    ensure_services_started(["security"])

    assert filter_user_communities(plain_user) is not None


def test_both_predicates_are_callable_from_a_template(
    app: Application, db: SQLAlchemy
) -> None:
    """The templates ask by name, so the names have to be registered.

    `is_site_admin` is a core jinja global, `can_manage` an SBE context
    processor -- `web/templates/macros/comment.html` is core and needs the
    first, `documents/document.html` is SBE and needs the second. Jinja raises
    on calling an undefined, so getting this wrong is a 500 on a page that no
    Python test renders.

    `db` is needed because `can_manage` asks the engine now, and the engine
    reads `permission_assignment`. It used to answer an anonymous user from a
    guard clause without a query; that guard is gone, because the engine
    supports assigning a permission to the ANONYMOUS role and a short-circuit
    here would silently disagree with it.
    """
    ensure_services_started(["security"])

    with app.test_request_context("/"):
        assert render_template_string("{{ is_site_admin() }}") == "False"
        assert render_template_string("{{ can_manage(current_user, None) }}") == "False"
