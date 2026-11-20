# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.core.models import comment as comments
from abilian.services.security import CREATE, DELETE, OWNER, READ, WRITE, security
from abilian.web import url_for

from .forms import CommentForm
from .views import COMMENT_BUTTON, bp as blueprint

if TYPE_CHECKING:
    from flask import Flask

    from abilian.core.models.subjects import User


class CommentExtension:
    """API for comments, installed as an application extension."""

    def __init__(self, app: Flask) -> None:
        app.extensions["comments"] = self
        app.register_blueprint(blueprint)

    def is_commentable(self, obj):
        return comments.is_commentable(obj)

    def for_entity(self, obj, check_commentable=False):
        return comments.for_entity(obj, check_commentable=check_commentable)

    def has_comments(self, obj):
        return bool(comments.for_entity(obj, check_commentable=True))

    def count(self, obj):
        return len(comments.for_entity(obj, check_commentable=True))

    #
    # current user capabilities
    #
    # A comment's permissions are the permissions of what it is a comment on,
    # except that its author may edit and delete their own. That exception does
    # not need a clause here: OWNER is a real role and `has_role` answers it
    # against `object.owner`, so passing it as an additional valid role says
    # "whoever may write this, plus whoever wrote it".

    # On the entity, inherited: a document's roles are its folders'.

    def can_read(self, user: User, entity):
        """True if `user` can read comments on entity."""
        return comments.may_read(user, entity) and security.has_permission(
            user, READ, obj=entity, inherit=True
        )

    def can_create(self, user: User, entity):
        """True if `user` can comment on entity."""
        return comments.may_read(user, entity) and security.has_permission(
            user, CREATE, obj=entity, inherit=True
        )

    def can_write(self, user: User, comment):
        """True if `user` can edit this comment."""
        return comments.may_read(user, comment.entity) and security.has_permission(
            user, WRITE, obj=comment, roles=OWNER
        )

    def can_delete(self, user: User, comment):
        """True if `user` can delete this comment."""
        return comments.may_read(user, comment.entity) and security.has_permission(
            user, DELETE, obj=comment, roles=OWNER
        )

    def get_form_context(self, obj):
        """Return a dict: form instance, action button, submit url...

        Used by macro m_comment_form(entity)
        """
        return {
            "url": url_for("comments.create", entity_id=obj.id),
            "form": CommentForm(),
            "buttons": [COMMENT_BUTTON],
        }
