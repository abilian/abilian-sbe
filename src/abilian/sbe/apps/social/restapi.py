"""
NOTE: this code is a legacy from the early days of the application,
and currently not used.
"""

import json

from flask import Blueprint, make_response, request
from flask_login import current_user, login_required

from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User
from abilian.core.util import get_params

from .models import Message

__all__ = ["restapi"]

restapi = Blueprint("restapi", __name__, url_prefix="/api")

# Util


def make_json_response(obj, response_code=200):
    if isinstance(obj, list):
        obj = [x.to_dict() if hasattr(x, "to_dict") else x for x in obj]

    if hasattr(obj, "to_json"):
        response = make_response(obj.to_json(), response_code)
    elif hasattr(obj, "to_dict"):
        response = make_response(json.dumps(obj.to_dict()), response_code)
    else:
        response = make_response(json.dumps(obj), response_code)
    response.mimetype = "application/json"
    return response


#
# Users
#


# [POST] /api/users/USER_ID	Create User Profile
@restapi.route("/users", methods=["POST"])
@login_required
def create_user():
    d = get_params(User.__editable__)
    user = User(**d)
    db.session.add(user)
    db.session.commit()
    return make_json_response(user, 201)


# [GET] /api/users	List Users in Your Organization
@restapi.route("/users")
@login_required
def list_users():
    # l = [ u.to_dict() for u in User.query.all() ]
    users = list(User.query.all())
    return make_json_response(users)


# [GET] /api/users/USER_ID	View User Profile
@restapi.route("/users/<int:user_id>")
@login_required
def get_user(user_id):
    user = User.query.get(user_id)
    return make_json_response(user)


# [GET] /api/users/USER_ID/messages	View Stream of Messages by User
@restapi.route("/users/<int:user_id>/messages")
@login_required
def user_stream(user_id):
    user = User.query.get(user_id)
    messages = Message.query.by_creator(user).all()
    # messages = list(user.messages)
    return make_json_response(messages)


# [PUT] /api/users/USER_ID	Update User Profile
@restapi.route("/users/<int:user_id>", methods=["PUT"])
@login_required
def update_user(user_id):
    user = User.query.get(user_id)
    d = get_params(User.__editable__)
    user.update(d)
    db.session.commit()
    return make_json_response(user)


# [DELETE] /api/users/USER_ID	Deactivate a User
@restapi.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id):
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    return make_response("", 204)


#
# Social graph: following
#


# [GET] /api/users/USER_ID/followers	View Followers of User
@restapi.route("/users/<int:user_id>/followers")
@login_required
def get_followers(user_id):
    user = User.query.get(user_id)
    followers = list(user.followers)
    return make_json_response(followers)


# [GET] /api/users/USER_ID/followees	View List of Users Being Followed
@restapi.route("/users/<int:user_id>/followees")
@login_required
def get_followees(user_id):
    user = User.query.get(user_id)
    followees = list(user.followees)
    return make_json_response(followees)


# [POST] /api/users/USER_ID/followers	Follow a User
@restapi.route("/users/<int:user_id>/followers", methods=["POST"])
@login_required
def follow(user_id):
    user = User.query.get(user_id)
    current_user.follow(user)
    db.session.commit()
    return make_json_response("", 204)


# [DELETE] /api/users/USER_ID/followers/CONTACT_USER_ID	Unfollow a User
@restapi.route(
    "/users/<int:user_id>/followers/<int:contact_user_id>", methods=["DELETE"]
)
@login_required
def unfollow(user_id, contact_user_id):
    user = User.query.get(user_id)
    current_user.unfollow(user)
    db.session.commit()
    return make_json_response("", 204)


#
# Social graph: groups
#


# [GET] /api/groups	Listing All Groups
@restapi.route("/groups")
@login_required
def list_groups():
    groups = list(Group.query.all())
    return make_json_response(groups)


# [GET] /api/groups/GROUP_ID	Show a Single Group
@restapi.route("/groups/<int:group_id>")
@login_required
def get_group(group_id):
    group = Group.query.get(group_id)
    return make_json_response(group)


# [GET] /api/groups/GROUP_ID/members	Listing Members of a Group
@restapi.route("/groups/<int:group_id>/members")
@login_required
def get_group_members(group_id):
    group = Group.query.get(group_id)
    return make_json_response(group.members)


# [GET] /api/group_memberships	Listing Group Memberships


# [POST] /api/groups	Create a Group
@restapi.route("/groups", methods=["POST"])
@login_required
def create_group():
    d = get_params(Group.__editable__)
    group = Group(**d)
    db.session.add(group)
    db.session.commit()
    return make_json_response(group, 201)


# [PUT] /api/groups/GROUP_ID	Updating Existing Group

# [DELETE] /api/groups/GROUP_ID/archive	Archiving a Group

# [DELETE] /api/groups/GROUP_ID	Destroy an Archived Message

#
# Messages
#


# [POST] /api/messages	Creating New Messages
@restapi.route("/messages", methods=["POST"])
@login_required
def create_message():
    d = get_params(Message.__editable__)
    message = Message(creator_id=current_user.id, **d)
    db.session.add(message)
    db.session.commit()
    return make_json_response(message, 201)


# [GET] /api/messages	Reading Stream Messages
@restapi.route("/messages")
@login_required
def get_messages():
    messages = list(Message.query.all())
    return make_json_response(messages)


# [GET] /api/messages/MESSAGE_ID	Read a Single Stream Message
@restapi.route("/messages/<int:message_id>")
@login_required
def get_message(message_id):
    message = Message.query.get(message_id)
    return make_json_response(message)


# [PUT] /api/messages/MESSAGE_ID	Updating Existing Messages
@restapi.route("/messages/<int:message_id>", methods=["PUT"])
@login_required
def update_message(message_id):
    message = Message.query.get(message_id)
    d = get_params(["content"])
    message.update(d)
    db.session.commit()
    return make_json_response(message)


# [DELETE] /api/messages/MESSAGE_ID	Destroy an existing message
@restapi.route("/messages/<int:message_id>", methods=["DELETE"])
@login_required
def delete_message(message_id):
    message = Message.query.get(message_id)
    db.session.delete(message)
    db.session.commit()
    return make_response("", 204)


#
# Likes
#
# TODO: use an "objects" namespace instead to make it generic?


# [POST] /api/messages/MESSAGE_ID/likes	Liking a Message
@restapi.route("/messages/<int:message_id>/likes", methods=["POST"])
@login_required
def like_message(message_id):
    pass


# [POST] /api/comments/COMMENT_ID/likes/LIKES_ID	Liking a Comment
@restapi.route("/comments/<int:comment_id>/likes", methods=["POST"])
@login_required
def like_comment(comment_id):
    pass


# [DELETE] /api/messages/MESSAGE_ID/likes/LIKES_ID	Un-liking a Message
@restapi.route("/messages/<int:message_id>/likes/<int:like_id>", methods=["DELETE"])
@login_required
def unlike_message(message_id, like_id):
    pass


# [DELETE] /api/comments/COMMENT_ID/likes/LIKES_ID
@restapi.route("/comments/<int:comment_id>/likes/<int:like_id>", methods=["DELETE"])
@login_required
def unlike_comment(comment_id, like_id):
    pass


#
# Search
#


# [GET] /api/messages/search	Searching Messages
@restapi.route("/search/messages")
@login_required
def search_messages():
    q = request.args.get("q")
    if not q:
        return make_json_response([])
    messages = list(Message.search_query(q).all())
    return make_json_response(messages)


# [GET] /api/users/search	Search Users in Your Company
@restapi.route("/search/users")
@login_required
def search_users():
    q = request.args.get("q")
    if not q:
        return make_json_response([])
    users = list(User.search_query(q).all())
    return make_json_response(users)


#
# Activity Streams
#
@restapi.route("/feed")
@login_required
def get_feed():
    pass
