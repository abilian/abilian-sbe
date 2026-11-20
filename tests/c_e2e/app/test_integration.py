# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Never, cast

from abilian.core.models.subjects import User
from abilian.services import get_service
from abilian.services.security import ADMIN, SecurityService
from abilian.web import url_for
from tests.util import ensure_services_started

from .conftest import ENDPOINTS_TO_IGNORE

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flask_sqlalchemy import SQLAlchemy
    from werkzeug.routing import Rule

    from abilian.app import Application


def all_rules_to_test(app: Application) -> Iterator[Rule]:
    rules = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue

        if rule.arguments:
            continue

        rules.append(rule)
    return sorted(rules, key=lambda r: r.endpoint)


#: Endpoints that answer a bare GET with something other than the default, and
#: why that is right.
EXPECTED_STATUS = {
    # Need a `q` of two characters or more.
    "admin.audit_search_users": 400,
    "communities.list_json2": 400,
    "social.users_json": 400,
    # Need the image's `md5`, which is what lets them be cached forever.
    "communities.community_default_image": 400,
    "images.user_default": 400,
    # Redirects to the first panel.
    "preferences.index": 302,
    # The feed moved to the home page, Mon fil.
    "social.home": 302,
}

#: What an anonymous visitor may get: the page, the login page, or a refusal.
ANONYMOUS_STATUSES = {200, 302, 403}


def test_all_simple_endpoints_with_no_login(client, app: Application) -> None:
    warnings.simplefilter("ignore")
    ensure_services_started(["security", "indexing"])

    failures = []
    for rule in all_rules_to_test(app):
        endpoint = rule.endpoint
        if endpoint in ENDPOINTS_TO_IGNORE:
            continue

        try:
            status = client.get(url_for(endpoint)).status_code
        except Exception as e:
            failures.append(f"{rule.rule} ({endpoint}): raised {e!r}")
            continue
        if status not in ANONYMOUS_STATUSES and status != EXPECTED_STATUS.get(endpoint):
            failures.append(f"{rule.rule} ({endpoint}): {status}")

    assert not failures, "\n".join(failures)


def test_all_simple_endpoints_as_admin(
    client, app: Application, db: SQLAlchemy
) -> None:
    warnings.simplefilter("ignore")
    ensure_services_started(["security", "indexing"])
    login_as_admin(client, db)

    failures = []
    for rule in all_rules_to_test(app):
        endpoint = rule.endpoint
        if endpoint in ENDPOINTS_TO_IGNORE:
            continue

        expected = EXPECTED_STATUS.get(endpoint, 200)
        try:
            status = client.get(url_for(endpoint)).status_code
        except Exception as e:
            failures.append(f"{rule.rule} ({endpoint}): raised {e!r}")
            continue
        if status != expected:
            failures.append(f"{rule.rule} ({endpoint}): {status}, expected {expected}")

    assert not failures, "\n".join(failures)


def test_login_as_admin(client, db: SQLAlchemy) -> None:
    login_as_admin(client, db)


def test_failed_login(client, db: SQLAlchemy) -> None:
    data = {"email": "test@example.com", "password": "admin"}
    r = client.post(url_for("login.login_post"), data=data)
    assert r.status_code == 401


#
# Util
#
def login_as_admin(client, db: SQLAlchemy) -> None:
    email = "admin@example.com"
    password = "secret"  # noqa: S105
    user = User(email=email, can_login=True, password=password)

    # Needed for grant_role to not raise an exception
    db.session.add(user)

    security = cast("SecurityService", get_service("security"))
    security.grant_role(user, ADMIN)

    db.session.add(user)
    db.session.flush()

    data = {"email": email, "password": password}
    r = client.post(url_for("login.login_post"), data=data)
    assert r.status_code == 302


def logout(client) -> Never:
    raise NotImplementedError
