from __future__ import absolute_import, print_function, unicode_literals

from unittest import skip

from flask import url_for

from abilian.sbe.testing import BaseTestCase


class TestsViews(BaseTestCase):
    no_login = True

    @skip("Doesn't work. Needs a real user.")
    def test_crm_notifications(self):
        response = self.client.get(url_for("preferences.crm_notifications"))
        assert response.status_code == 200
