# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals

from abilian.web import url_for

from abilian.sbe.testing import BaseTestCase


class TestViews(BaseTestCase):
    no_login = True

    def test_all_registered_urls(self):

        SKIP = frozenset(
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

        rules = sorted(self.app.url_map.iter_rules(), key=lambda x: x.endpoint)
        for rule in rules:

            if "GET" not in rule.methods:
                continue

            if rule.arguments:
                continue

            # FIXME. Skip several exceptions.
            if rule.endpoint in SKIP:
                continue

            # These endpoints expect a parameter ('q') that we don't provide
            if rule.endpoint.endswith("list_json2"):
                continue

            url = url_for(rule.endpoint)

            if "/ajax/" in url:
                continue

            print(rule.endpoint, url)

            try:
                response = self.client.get(url)
                err_msg = "Bad link: {} (status={})".format(url, response.status_code)
                assert response.status_code in (200, 302), err_msg
            except BaseException:
                print("Problem with url: {}".format(url))
                raise
