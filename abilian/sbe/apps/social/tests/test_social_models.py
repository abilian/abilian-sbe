from abilian.core.entities import all_entity_classes
from abilian.core.models.subjects import Group, User
from abilian.sbe.apps.social.models import Message, PrivateMessage


def check_editable(object):
    if hasattr(object, "__editable__"):
        for k in object.__editable__:
            assert hasattr(object, k)


def test_user() -> None:
    user = User(
        first_name="John",
        last_name="Test User",
        email="test@example.com",
        password="toto",
    )
    check_editable(user)

    assert "John Test User" == user.name
    assert "John Test User" == str(user)
    # self.assertEquals(len(user.messages), 0)


def test_user_follow() -> None:
    # id is provided by DB (which is not used in this test), and is required for
    # having in (user1 != user2) == True
    user1 = User(
        id=1,
        first_name="John",
        last_name="Test User 1",
        email="test1@example.com",
        password="toto",
    )
    user2 = User(
        id=2,
        first_name="Joe",
        last_name="Test User 2",
        email="test2@example.com",
        password="toto",
    )

    assert len(user1.followers) == 0
    assert len(user1.followees) == 0
    assert len(user2.followers) == 0
    assert len(user2.followees) == 0

    user1.follow(user2)

    assert user1.is_following(user2)
    assert len(user2.followers) == 1
    assert len(user1.followees) == 1
    assert len(user2.followees) == 0
    assert len(user1.followers) == 0
    assert user2 in user1.followees

    user1.unfollow(user2)

    assert not user1.is_following(user2)
    assert len(user1.followers) == 0
    assert len(user1.followees) == 0
    assert len(user2.followers) == 0
    assert len(user2.followees) == 0
    assert user2 not in user1.followers


def test_group() -> None:
    user = User(
        first_name="John",
        last_name="Test User",
        email="test@example.com",
        password="toto",
    )
    group = Group(name="Group 1")

    user.join(group)

    assert user.is_member_of(group)
    assert len(group.members) == 1
    assert len(user.groups) == 1
    assert group.members == {user}
    assert user.groups == {group}

    user.leave(group)

    assert not user.is_member_of(group)
    assert len(group.members) == 0
    assert len(user.groups) == 0


def test_private_message() -> None:
    pm = PrivateMessage(creator_id=0, recipient_id=0)
    check_editable(pm)


# TODO: implement status updates (aka messages)
# def test_status_update(db):
#     user = User(
#         first_name="John",
#         last_name="Test User",
#         email="test@example.com",
#         password="toto",
#     )
#     db.session.commit()
#     assert len(user.messages) == 0
#
#     message = Message()
#     message.author = user
#     check_editable(message)
#
#     db.session.commit()
#     assert len(user.messages) == 1
#     assert user.messages[0] == message
#     assert message.author_id == user.uid


def test_tags() -> None:
    m = Message(content="abc #123 #cde #voilà_l_été #789")
    assert m.tags == ["123", "cde", "voilà_l_été", "789"]


def test_get_all_entity_classes() -> None:
    classes = all_entity_classes()
    assert Message in classes
    assert PrivateMessage in classes
