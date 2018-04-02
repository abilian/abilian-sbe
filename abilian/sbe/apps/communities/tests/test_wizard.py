# Note: this test suite is using pytest instead of the unittest-based scaffolding
# provided by SBE. Hopefully one day all of SBE will follow.
from __future__ import absolute_import, print_function, unicode_literals

from tempfile import NamedTemporaryFile

import pytest
from abilian.core.models.subjects import User
from flask import g

from abilian.sbe.apps.communities.models import READER, Community
from abilian.sbe.apps.communities.views.wizard import wizard_extract_data, \
    wizard_read_csv


@pytest.fixture
def csv_file():
    # create a tmp csv file
    csv = NamedTemporaryFile("w+", suffix=".csv", prefix="tmp_", delete=False)
    csv.write("user_1@example.com;userone;userone;manager\n")
    csv.write("user_2@example.com;usertwo;usertwo;member\n")
    csv.write("user_7@example.com;userseven;userseven;member\n")

    # writing a wrong line
    csv.write("user1@example.com;userthree;userthree\n")
    csv.write("example.com;example;userfour;member\n")

    csv.seek(0)
    csv.filename = csv.name

    return csv


def test_wizard_read_csv(csv_file):
    wizard_read = wizard_read_csv(csv_file)

    assert wizard_read == [
        {
            'first_name': 'userone',
            'last_name': 'userone',
            'role': 'manager',
            'email': 'user_1@example.com',
        },
        {
            'first_name': 'usertwo',
            'last_name': 'usertwo',
            'role': 'member',
            'email': 'user_2@example.com',
        },
        {
            'first_name': 'userseven',
            'last_name': 'userseven',
            'role': 'member',
            'email': 'user_7@example.com',
        },
    ]


def test_wizard_extract_data(db, csv_file):
    session = db.session
    community = Community(name='Hp')
    g.community = community

    user1 = User(email='user_1@example.com')
    user2 = User(email='user_2@example.com')
    user3 = User(email='user_3@example.com')

    new_emails = [
        "user_1@example.com",
        "user_2@example.com",
        "user_3@example.com",
        "user_4@example.com",
        "user_5@example.com",
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

    # check wizard function in case of email list
    existing_accounts_objects, existing_members_objects, accounts_list \
        = wizard_extract_data(new_emails)
    assert set(existing_accounts_objects) == {user2, user3}
    assert existing_members_objects == [user1]

    def sorter(x):
        return x['email']

    assert sorted(
        accounts_list,
        key=sorter,
    ) == sorted(
        [
            {
                'status': 'existing',
                'first_name': None,
                'last_name': None,
                'role': 'member',
                'email': 'user_2@example.com',
            },
            {
                'status': 'existing',
                'first_name': None,
                'last_name': None,
                'role': 'member',
                'email': 'user_3@example.com',
            },
            {
                'status': 'new',
                'first_name': '',
                'last_name': '',
                'role': 'member',
                'email': 'user_5@example.com',
            },
            {
                'status': 'new',
                'first_name': '',
                'last_name': '',
                'role': 'member',
                'email': 'user_4@example.com',
            },
        ],
        key=sorter,
    )

    # check wizard function in case of csv file
    existing_accounts_objects, existing_members_objects, accounts_list \
        = wizard_extract_data(wizard_read_csv(csv_file), is_csv=True)

    assert existing_accounts_objects == {
        "csv_roles": {
            "user_1@example.com": "manager",
            "user_2@example.com": "member",
            "user_7@example.com": "member",
        },
        "account_objects": [user2],
    }
    assert existing_members_objects == [user1]
    assert sorted(
        accounts_list,
        key=sorter,
    ) == sorted(
        [
            {
                'status': 'existing',
                'first_name': None,
                'last_name': None,
                'role': 'member',
                'email': 'user_2@example.com',
            },
            {
                'status': 'new',
                'first_name': 'userseven',
                'last_name': 'userseven',
                'role': 'member',
                'email': 'user_7@example.com',
            },
        ],
        key=sorter,
    )
