# Note: this test suite is using pytest instead of the unittest-based scaffolding
# provided by SBE. Hopefully one day all of SBE will follow.
from tempfile import NamedTemporaryFile

from flask import g

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import READER, Community
from abilian.sbe.apps.communities.views.wizard import wizard_extract_data, \
    wizard_read_csv


def test_wizard_read_csv():
    # create a tmp csv file
    csv = NamedTemporaryFile(suffix=".csv", prefix="tmp_", delete=False)
    csv.write("user1@example.com;userone;userone;manager\n")
    csv.write("user1@example.com;usertwo;usertwo;member\n")

    # writing a wrong line
    csv.write("user1@example.com;userthree;userthree\n")
    csv.write("example.com;example;userfour;member\n")

    csv.seek(1)
    csv.filename = csv.name.split("/")[-1]
    wizard_read = wizard_read_csv(csv)

    assert wizard_read == [{
        'first_name': 'userone',
        'last_name': 'userone',
        'role': 'manager',
        'email': 'ser1@example.com'
    }, {
        'first_name': 'usertwo',
        'last_name': 'usertwo',
        'role': 'member',
        'email': 'user1@example.com'
    }]


def test_wizard_extract_data(db_session):
    session = db_session

    community = Community(name=u'Hp')
    g.community = community

    user1 = User(email=u'user_1@example.com', password='azerty', can_login=True)
    user2 = User(email=u'user_2@example.com', password='azerty', can_login=True)
    user3 = User(email=u'user_3@example.com', password='azerty', can_login=True)

    new_emails = [
        u"user_1@example.com", u"user_2@example.com", u"user_3@example.com",
        u"user_4@example.com", u"user_5@example.com"
    ]

    # creating community
    session.add(community)

    # creating users
    session.add(user1)
    session.add(user2)
    session.add(user3)
    session.flush()

    # add user1 to the community
    community.set_membership(user1, READER)
    session.flush()

    # check wizard function
    existing_accounts_objects, existing_members_objects, accounts_list = wizard_extract_data(
        new_emails)
    assert set(existing_accounts_objects) == {user2, user3}
    assert existing_members_objects == [user1]
    assert sorted(accounts_list) == sorted([{
        'status': 'existing',
        'first_name': None,
        'last_name': None,
        'role': 'member',
        'email': u'user_2@example.com'
    }, {
        'status': 'existing',
        'first_name': None,
        'last_name': None,
        'role': 'member',
        'email': u'user_3@example.com'
    }, {
        'status': 'new',
        'first_name': '',
        'last_name': '',
        'role': 'member',
        'email': u'user_5@example.com'
    }, {
        'status': 'new',
        'first_name': '',
        'last_name': '',
        'role': 'member',
        'email': u'user_4@example.com'
    }])
