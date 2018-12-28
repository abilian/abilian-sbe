# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals

from abilian.core.models.subjects import User

from abilian.sbe.apps.communities.models import READER, Community
from abilian.sbe.testing import BaseTestCase


class CommunityBaseTestCase(BaseTestCase):

    no_login = True

    def setUp(self):
        super(CommunityBaseTestCase, self).setUp()
        self.community = Community(name="My Community")
        self.session.add(self.community)
        self.session.flush()
