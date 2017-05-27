# Note: this test suite is using pytest instead of the unittest-based scaffolding
# provided by SBE. Hopefully one day all of SBE will follow.

from datetime import datetime, timedelta

import pytest

import abilian.i18n
from abilian.core.models.subjects import User
from abilian.core.signals import activity
from abilian.sbe.app import create_app
from .base import CommunityIndexingTestCase
from abilian.sbe.apps.communities.views import _wizard_check_query, wizard_read_csv


@pytest.yield_fixture
def app():
    app = create_app()
    babel = abilian.i18n.babel
    babel.locale_selector_func = None
    yield app
    activity._clear_state()


class WizardTest(CommunityIndexingTestCase):

    def wizard_test_empty_list(self):
        wizard_emails = []
        existing_accounts_objects, existing_members_objects, accounts_list = _wizard_check_query(wizard_emails)
        assert existing_accounts_objects == []
        assert existing_members_objects == []
        assert accounts_list == []

    def wizard_test_check_emails(self):
        wizard_emails = ["user_1@example.com", "no_community@example.com"]
        existing_accounts_objects, existing_members_objects, accounts_list = _wizard_check_query(wizard_emails)
        assert existing_accounts_objects == [self.user_no_community]
        assert existing_members_objects == [self.user]
        assert accounts_list == []
