# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.core.models import attachment as attachments
from abilian.services.security import CREATE, DELETE, READ, WRITE, security
from abilian.web import url_for

from .forms import AttachmentForm
from .views import UPLOAD_BUTTON, bp as blueprint

if TYPE_CHECKING:
    from flask import Flask

    from abilian.core.models.subjects import User

_MANAGER_ATTR = "__attachments_manager__"


class AttachmentExtension:
    """API for comments, installed as an application extension."""

    def __init__(self, app: Flask) -> None:
        app.extensions["attachments"] = self
        app.register_blueprint(blueprint)

    def manager(self, obj):
        """Returns the :class:`AttachmentsManager` instance for this object."""
        manager = getattr(obj, _MANAGER_ATTR, None)
        if manager is None:
            manager = AttachmentsManager()
            setattr(obj.__class__, _MANAGER_ATTR, manager)

        return manager

    def supports_attachments(self, obj):
        return self.manager(obj).supports_attachments(obj)

    def for_entity(self, obj, check_support_attachments=False):
        return self.manager(obj).for_entity(
            obj, check_support_attachments=check_support_attachments
        )

    def has_attachments(self, obj):
        return self.manager(obj).has_attachments(obj)

    def count(self, obj):
        return self.manager(obj).count(obj)

    def get_form_context(self, obj):
        """Return a dict: form instance, action button, submit url...

        Used by macro m_attachment_form(entity)
        """
        return self.manager(obj).get_form_context(obj)


class AttachmentsManager:
    """Allow customization of attachments form.

    can be used as class decorator
    """

    Form = AttachmentForm

    def __init__(self, Form=AttachmentForm) -> None:
        self.Form = Form

    def __call__(self, Model):
        setattr(Model, _MANAGER_ATTR, self)
        return Model

    def supports_attachments(self, obj):
        return attachments.supports_attachments(obj)

    def for_entity(self, obj, check_support_attachments=False):
        return attachments.for_entity(
            obj, check_support_attachments=check_support_attachments
        )

    def has_attachments(self, obj):
        return bool(self.for_entity(obj, check_support_attachments=True))

    def count(self, obj):
        return len(self.for_entity(obj, check_support_attachments=True))

    def get_form_context(self, obj):
        """Return a dict: form instance, action button, submit url...

        Used by macro m_attachment_form(entity)
        """
        return {
            "url": url_for("attachments.create", entity_id=obj.id),
            "form": self.Form(),
            "buttons": [UPLOAD_BUTTON],
        }

    #
    # current user capabilities
    #
    def can_read(self, user: User, entity):
        """True if `user` can read attachments on entity."""
        return security.has_permission(user, READ, obj=entity)

    def can_write(self, user: User, entity):
        """True if `user` can write attachments on entity."""
        return security.has_permission(user, WRITE, obj=entity)

    # These asked WRITE, so "may add" and "may remove" were one question while
    # the names said two. CREATE, DELETE and WRITE share a default role set --
    # {ADMIN, MANAGER, WRITER}, service.py:71 -- so asking each its own
    # permission answers the same today, and lets a PermissionAssignment
    # separate them without touching this code.
    def can_create(self, user: User, entity):
        """True if `user` can add attachments."""
        return security.has_permission(user, CREATE, obj=entity)

    def can_delete(self, user: User, entity):
        """True if `user` can delete attachments."""
        return security.has_permission(user, DELETE, obj=entity)
