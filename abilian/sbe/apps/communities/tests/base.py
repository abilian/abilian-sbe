from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import READER, Community
from abilian.sbe.testing import BaseTestCase


class CommunityBaseTestCase(BaseTestCase):

    no_login = True

    def setUp(self):
        super(CommunityBaseTestCase, self).setUp()
        self.community = Community(name=u"My Community")
        self.session.add(self.community)
        self.session.flush()


class CommunityIndexingTestCase(CommunityBaseTestCase):
    """
    Testcase for testing indexing and searching of community content.
    """

    no_login = False
    SERVICES = ('security', 'indexing',)

    def setUp(self):
        super(CommunityIndexingTestCase, self).setUp()
        self.svc = self.app.services['indexing']
        self.user = User(email=u'user_1@example.com',
                         password='azerty',
                         can_login=True)
        self.session.add(self.user)
        self.community.set_membership(self.user, READER)
        self.c2 = Community(name=u'Other community')
        self.session.add(self.c2)
        self.user_c2 = User(email=u'user_2@example.com',
                            password='azerty',
                            can_login=True)
        self.session.add(self.user_c2)
        self.c2.set_membership(self.user_c2, READER)

        self.user_no_community = User(email=u'no_community@example.com',
                                      password='azerty',
                                      can_login=True)
        self.session.add(self.user_no_community)
        self.session.commit()
