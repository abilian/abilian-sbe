from __future__ import absolute_import, print_function, unicode_literals

import re
import traceback
import warnings

from abilian.testing.fixtures import admin_user, login_admin
from abilian.web import url_for
from pytest import mark

ENDPOINTS_TO_SKIP = frozenset(
    [
        "admin.audit_search_users",
        "search.search_main",
        "search.live",
        "notifications.debug_social",
        "social.groups_json",
        "social.groups_new",
        "social.users_json",
        "social.users_dt_json",
        "communities.community_default_image",
        "images.user_default",
    ]
)

PATTERNS_TO_SKIP = [r"^.*\.list_json2$", r"^setup\..*$"]


def get_all_rules(app):
    rules = sorted(app.url_map.iter_rules(), key=lambda x: x.endpoint)

    for rule in rules:
        if "GET" not in rule.methods:
            continue

        if rule.arguments:
            continue

        endpoint = rule.endpoint
        print(endpoint)

        # Skip several exceptions.
        if endpoint in ENDPOINTS_TO_SKIP:
            continue

        if any(re.match(p, endpoint) for p in PATTERNS_TO_SKIP):
            continue

        url = url_for(endpoint)

        if "/ajax/" in url:
            continue

        yield rule


@mark.usefixtures("req_ctx")
def test_all_registered_urls(app, db, client):
    warnings.filterwarnings("ignore")

    rules = get_all_rules(app)
    user = admin_user(db)

    for rule in rules:
        login_admin(user, client)

        endpoint = rule.endpoint
        url = url_for(endpoint)
        try:
            response = client.get(url)
            assert response.status_code in (
                200,
                302,
            ), "Bad link: {} (status={})".format(url, response.status_code)
        except BaseException:
            msg = "Problem with endpoint: {} / url: {}".format(endpoint, url)
            print(msg)
            traceback.print_exc()
            raise
