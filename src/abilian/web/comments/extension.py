# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import current_user

from abilian.core.models import comment as comments
from abilian.services.security import CREATE, DELETE, OWNER, READ, WRITE, security
from abilian.web import url_for

from .forms import CommentForm
from .views import COMMENT_BUTTON, bp as blueprint

if TYPE_CHECKING:
    from flask import Flask


class CommentExtension:
    """API for comments, installed as an application extension.

    It is also available in templates as `comments`.
    """

    def __init__(self, app: Flask) -> None:
        app.extensions["comments"] = self
        app.add_template_global(self, "comments")
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

    def can_read(self, entity):
        """True if user can read comments on entity."""
        return security.has_permission(current_user, READ, obj=entity)

    def can_create(self, entity):
        """True if user can comment on entity."""
        return security.has_permission(current_user, CREATE, obj=entity)

    def can_write(self, comment):
        """True if user can edit this comment."""
        return security.has_permission(current_user, WRITE, obj=comment, roles=OWNER)

    def can_delete(self, comment):
        """True if user can delete this comment."""
        return security.has_permission(current_user, DELETE, obj=comment, roles=OWNER)

    def get_form_context(self, obj):
        """Return a dict: form instance, action button, submit url...

        Used by macro m_comment_form(entity)
        """
        return {
            "url": url_for("comments.create", entity_id=obj.id),
            "form": CommentForm(),
            "buttons": [COMMENT_BUTTON],
        }
