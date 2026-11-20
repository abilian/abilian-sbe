# Copyright (c) 2012-2024, Abilian SAS

"""Extensions to WTForms fields, widgets and validators."""

from __future__ import annotations

import typing
from collections import OrderedDict
from functools import partial
from typing import Any, Self

from flask import g, has_app_context
from flask_login import current_user
from flask_wtf import FlaskForm
from loguru import logger
from wtforms import Field, HiddenField
from wtforms_alchemy import model_form_factory

from abilian.core.entities import Entity
from abilian.core.logger_patch import patch_logger
from abilian.i18n import _, _n

from .widgets import DefaultViewWidget

if typing.TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.services.security import Permission
    from abilian.web.forms import FormPermissions


#  setup Form class with babel support
class _BabelTranslation:
    def gettext(self, string: str) -> str:
        return _(string)

    def ngettext(self, singular, plural, n):
        return _n(singular, plural, n)


BabelTranslation = _BabelTranslation()


class FormContext:
    """Allows :class:`forms <Form>` to set a context during instanciation, so
    that subforms used in formfields / listformfields / etc can perform proper
    field filtering according to original permission and user passed to top
    form `__init__` method."""

    permission: Permission | None
    user: User | None
    obj: Any

    def __init__(
        self,
        permission: Permission | None = None,
        user: User | None = None,
        obj: Any = None,
    ) -> None:
        self.permission = permission
        self.user = user
        self.obj = obj

    def __enter__(self) -> Self:
        if not has_app_context():
            return self

        self.__existing = getattr(g, "__form_ctx__", None)
        if self.__existing:
            if self.permission is None:
                self.permission = self.__existing.permission

            if self.user is None:
                self.user = self.__existing.user

            if self.obj is None or not isinstance(self.obj, Entity):
                self.obj = self.__existing.obj

        if self.user is None:
            self.user = current_user

        g.__form_ctx__ = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not has_app_context():
            return

        g.__form_ctx__ = self.__existing


class Form(FlaskForm):
    _groups: dict[str, list[str]] = OrderedDict()

    #: :class:`FormPermissions` instance
    _permissions: FormPermissions | None = None

    def __init__(self, *args, **kwargs) -> None:
        permission = kwargs.pop("permission", None)
        user = kwargs.pop("user", None)
        obj = kwargs.get("obj")
        form_ctx = FormContext(permission=permission, user=user, obj=obj)

        if kwargs.get("csrf_enabled") is None and not has_app_context():
            # form instanciated without app context and without explicit csrf
            # parameter: disable csrf since it requires current_app.
            #
            # If there is a prefix, it's probably a subform (in a fieldform of
            # fieldformlist): csrf is not required. If there is no prefix: let error
            # happen.
            if kwargs.get("prefix"):
                kwargs["csrf_enabled"] = False

        with form_ctx as ctx:
            super().__init__(*args, **kwargs)
            self._field_groups = {}  # map field -> group

            if not isinstance(self.__class__._groups, OrderedDict):
                self.__class__._groups = OrderedDict(self.__class__._groups)

            for label, fields in self._groups.items():
                self._groups[label] = list(fields)
                self._field_groups.update(dict.fromkeys(fields, label))

            if ctx.permission and self._permissions is not None:
                # we are going to alter groups: copy dict on instance to preserve class
                # definition
                self._groups = OrderedDict()
                for label, fields in self.__class__._groups.items():
                    self._groups[label] = list(fields)

                has_permission = partial(
                    self._permissions.has_permission,
                    ctx.permission,
                    obj=ctx.obj,
                    user=ctx.user,
                )
                empty_form = not has_permission()

                for field_name in list(self._fields):
                    if empty_form or not has_permission(field=field_name):
                        logger.debug(
                            "{class_name}(permission={permission}): "
                            "field {field_name}: removed",
                            class_name=self.__class__.__name__,
                            permission=repr(ctx.permission),
                            field_name=repr(field_name),
                        )
                        del self[field_name]
                        group = self._field_groups.get(field_name)
                        if group:
                            self._groups[group].remove(field_name)

    def _get_translations(self) -> _BabelTranslation:
        return BabelTranslation

    def _fields_for_group(self, group):
        for group_name, field_names in self._groups:
            if group == group_name:
                fields = field_names
                break
        else:
            msg = f"Group {group!r} not found"
            raise ValueError(msg)
        return fields

    def _has_required(self, group=None, fields=()):
        if group is not None:
            fields = self._fields_for_group(group)
        return any(self[f].flags.required for f in fields)

    def _count_errors(self, group=None, fields=()):
        if group is not None:
            fields = self._fields_for_group(group)
        return len([1 for f in fields if self[f].errors])


ModelForm = model_form_factory(Form)

# PATCH wtforms.field.core.Field ####################
_PATCHED = False

if not _PATCHED:
    Field.view_template = None

    _wtforms_field_init = Field.__init__

    def _core_field_init(self: Any, *args: Any, **kwargs: Any) -> None:
        view_widget = None
        if "view_widget" in kwargs:
            view_widget = kwargs.pop("view_widget")

        _wtforms_field_init(self, *args, **kwargs)
        if view_widget is None:
            view_widget = self.widget

        self.view_widget = view_widget

    patch_logger.info(Field.__init__)
    Field.__init__ = _core_field_init
    del _core_field_init

    def _core_field_repr(self) -> str:
        """`__repr__` that shows the name of the field instance.

        Useful for tracing field errors (like in Sentry).
        """
        return f"<{self.__class__.__module__}.{self.__class__.__name__} at 0x{id(self):x} name={self.name!r}>"

    patch_logger.info(f"{Field.__module__}.Field.__repr__")
    Field.__repr__ = _core_field_repr
    del _core_field_repr

    #  support 'widget_options' for some custom widgets
    _wtforms_field_render = Field.__call__

    def _core_field_render(self, **kwargs):
        if "widget_options" in kwargs and not kwargs["widget_options"]:
            kwargs.pop("widget_options")

        return _wtforms_field_render(self, **kwargs)

    patch_logger.info(Field.__call__)
    Field.__call__ = _core_field_render
    del _core_field_render

    def render_view(self, **kwargs):
        """Render data."""
        if "widget_options" in kwargs and not kwargs["widget_options"]:
            kwargs.pop("widget_options")

        if hasattr(self.view_widget, "render_view"):
            return self.view_widget.render_view(self, **kwargs)

        return DefaultViewWidget().render_view(self, **kwargs)

    patch_logger.info(f"Add method {Field.__module__}.Field.render_view")
    Field.render_view = render_view
    del render_view

    def is_hidden(self: Any) -> bool:
        """WTForms is not consistent with hidden fields, since `flags.hidden`
        is not set on `HiddenField` :-("""
        return self.flags.hidden or isinstance(self, HiddenField)

    patch_logger.info(f"Add method {Field.__module__}.Field.is_hidden")
    Field.is_hidden = property(is_hidden)
    del is_hidden

    _PATCHED = True
# END PATCH wtforms.field.core.Field #################
