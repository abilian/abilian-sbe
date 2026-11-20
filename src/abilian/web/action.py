# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from flask import current_app, g
from flask.signals import appcontext_pushed
from jinja2 import Template
from loguru import logger
from markupsafe import Markup

from abilian.core.singleton import UniqueName
from abilian.web import csrf
from abilian.web.util import url_for

if TYPE_CHECKING:
    from collections.abc import Callable

    from flask.app import Flask

__all__ = (
    "ACTIVE",
    "DISABLED",
    "ENABLED",
    "Action",
    "ActionGroup",
    "ActionGroupItem",
    "ButtonAction",
    "DynamicIcon",
    "Endpoint",
    "FAIcon",
    "Glyphicon",
    "ModalActionMixin",
    "StaticIcon",
    "actions",
    "getset",
)


class Status(UniqueName):
    """Action UI status names."""


#: default action status: show in UID, usable, not marked "current"
ENABLED = Status("enabled")
#: action is "active" or "current". For example the current navigation item.
ACTIVE = Status("active")
#: action should be shown in a disabled state
DISABLED = Status("disabled")


def getset(f: Callable) -> property:
    """Shortcut for a custom getter/ standard setter.

    Usage::

      @getset
      def my_property(self, value=None):
          if value is None:
              return getter_value
          set_value(value)

    Default value for `value` should be any marker that helps distinguish
    between getter or setter mode. If None is not appropriate a good approach is
    to use a unique object instance::

      MARK = object()
      # test like this
      if value is MARK:
        # getter mode
    """
    return property(f, f)


class Icon:
    """Base abstract class for icons."""

    def __html__(self):
        raise NotImplementedError

    def __str__(self) -> str:
        return self.__html__()


class NamedIconBase(Icon):
    """Renders markup for named icons set."""

    template: Template

    def __init__(self, name: str = "") -> None:
        self.name = name

    def __html__(self) -> str:
        return self.template.render(name=self.name)


class Glyphicon(NamedIconBase):
    """Renders markup for bootstrap's glyphicons (deprecated, use FAIcon instead)."""

    template = Template('<i class="fa fa-{{ name }}"></i>')


class FAIcon(NamedIconBase):
    """Renders markup for FontAwesome icons."""

    template = Template('<i class="fa fa-{{ name }}"></i>')


class FAIconStacked(NamedIconBase):
    """Stacked FA icons."""

    template = Template(
        '<span class="fa-stack {%- if stack_class %} {{ stack_class }}'
        '{%- endif %}">\n'
        '  <i class="fa fa-{{ name }}"></i>\n'
        '  <i class="fa fa-{{ second }}"></i>\n'
        "</span>"
    )

    def __init__(self, name, second, stack="") -> None:
        """
        @param name: first icon name, support additional css classes.

        @param second: second icon. Can be 'ban fa-stack-2x text-danger' for
        example.

        @param stack: additional class on top-level element, i.e 'fa-lg'.
        """
        if "fa-stack-" not in name:
            name += " fa-stack-1x"
        if "fa-stack-" not in second:
            second += " fa-stack-1x"

        super().__init__(name)
        self.second = second
        self.stack = stack

    def __html__(self):
        return self.template.render(
            name=self.name, second=self.second, stack_class=self.stack
        )


class DynamicIcon(Icon):
    template = Template(
        '<img {%- if css %} class="{{ css }}"{% endif %} '
        'src="{{ url }}" alt="" '
        'width="{{ width }}" height="{{ height }}" />'
    )

    def __init__(
        self,
        endpoint: str | Callable | None = None,
        *,
        width: int = 12,
        height: int = 12,
        css: str = "",
        size: int | None = None,
        url_args: Callable | None = None,
        **fixed_url_args,
    ) -> None:
        self.endpoint = endpoint
        self.css = css
        self.fixed_url_args = {}
        self.fixed_url_args.update(fixed_url_args)
        self.url_args_callback = url_args

        if size is not None:
            width = height = size

        self.width = width
        self.height = height

    def get_url_args(self) -> dict[str, str]:
        kw = {}
        kw.update(self.fixed_url_args)
        return kw

    def __html__(self) -> str:
        endpoint = self.endpoint
        if callable(endpoint):
            endpoint = endpoint()

        url_args = self.get_url_args()
        if self.url_args_callback is not None:
            url_args = self.url_args_callback(self, url_args)

        return self.template.render(
            url=url_for(endpoint, **url_args),
            width=self.width,
            height=self.height,
            css=self.css,
        )


class StaticIcon(DynamicIcon):
    """Renders markup for icon located in static folder served by `endpoint`.

    Default endpoint is application static folder.
    """

    def __init__(
        self,
        filename: str,
        *,
        endpoint: str = "static",
        width: int = 12,
        height: int = 12,
        css: str = "",
        size: int | None = None,
    ) -> None:
        super().__init__(
            endpoint,
            width=width,
            height=height,
            css=css,
            size=size,
            filename=filename,
        )


class Endpoint:
    # FIXME: *args doesn't seem to be relevant.
    def __init__(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.name = name
        self.args = args
        self.kwargs = kwargs

    def get_kwargs(self) -> dict[str, str]:
        """Hook for subclasses.

        The key and values in the returned dictionnary can be safely
        changed without side effects on self.kwargs (provided you don't
        alter mutable values, like calling list.pop()).
        """
        return self.kwargs.copy()

    def __str__(self) -> str:
        return str(url_for(self.name, **self.get_kwargs()))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r}, *{self.args!r}, **{self.kwargs!r})"


class Action:
    """Action interface."""

    Endpoint = Endpoint

    _title: str
    _description: str
    _icon: str | Icon | None
    _url: str | Callable

    CSS_CLASS = "action action-{category} action-{category}-{name}"

    template_string = (
        '<a class="{{ action.css_class }}" href="{{ url }}">'
        "{%- if action.icon %}{{ action.icon }} {% endif %}"
        "{{ action.title }}"
        "</a>"
    )

    def __init__(
        self,
        category: str,
        name: str,
        title: str = "",
        *,
        description: str = "",
        icon: str | Icon | None = None,
        url: str | Callable = "",
        endpoint: Endpoint | str | None = None,
        condition: Callable | None = None,
        status: Any | None = None,
        template: Any | None = None,
        template_string: Any | None = None,
        button: Any | None = None,
        css: Any | None = None,
    ) -> None:
        """
        :param endpoint: A :class:`Endpoint` instance, a string for a simple
        endpoint, a tuple ``(endpoint_name, kwargs)`` or a callable which
        accepts a : context dict and returns one of those a valid values.

        :param condition: A boolean (or something that can be converted
        to boolean), or a callable which accepts a context dict as parameter.
        See :meth:`available`.

        :param button: if not `None`, a valid `btn` class (i.e `default`,
        `primary`...)

        :param css: additional css class string

        :param template: optional: a template file name or a list of filenames.

        :param template_string: template_string to use. Defaults to
        `Action.template_string`
        """
        self.category = category
        self.name = name

        if button is not None:
            btn_colors = {
                "default": "text-gray-700 bg-white border border-gray-300 hover:bg-gray-50",
                "primary": "text-white bg-blue-600 hover:bg-blue-700",
                "success": "text-white bg-green-600 hover:bg-green-700",
                "danger": "text-white bg-red-600 hover:bg-red-700",
                "warning": "text-white bg-yellow-600 hover:bg-yellow-700",
                "info": "text-white bg-cyan-600 hover:bg-cyan-700",
            }
            btn_class = btn_colors.get(button, btn_colors["default"])
            self.CSS_CLASS += f" inline-flex items-center px-4 py-2 text-sm font-medium rounded-md {btn_class}"
        if css is not None:
            self.CSS_CLASS = f"{self.CSS_CLASS} {css}"
        self._build_css_class()

        self._title = title
        self._description = description
        if isinstance(icon, str):
            icon = Glyphicon(icon)
        self._icon = icon
        self._url = url
        self._status = Status(status) if status is not None else ENABLED
        self._endpoint = endpoint
        if not callable(endpoint) and not isinstance(endpoint, Endpoint):
            # property getter will make it an Endpoint instance
            self.endpoint = self.endpoint
        self.condition = condition

        self._enabled = True
        self.template = template
        if template_string:
            self.template_string = template_string

    #: ui status. A :class:`Status` instance
    @getset
    def status(self, value=None):
        status = self._status
        if value is not None:
            self._status = status = Status(value)
        return status

    #: Boolean. Disabled actions are unconditionnaly skipped.
    @getset
    def enabled(self, value: bool | None = None) -> bool:
        enabled = self._enabled
        if value is not None:
            assert isinstance(value, bool)
            self._enabled = enabled = value
        return enabled

    def _get_and_call(self, attr: str) -> Any:
        attr = f"_{attr}"
        value = getattr(self, attr)
        if callable(value):
            value = value(actions.context)
        return value

    @property
    def title(self) -> str:
        return self._get_and_call("title")

    @title.setter
    def title(self, title: str) -> None:
        self._title = title

    def _build_css_class(self) -> None:
        # Sanitize only the interpolated identifiers. The utility classes appended
        # to CSS_CLASS legitimately contain ":" (Tailwind variants such as
        # "hover:bg-blue-700") and "/" (opacity modifiers such as "bg-black/50"),
        # which sanitizing the whole string would silently mangle.
        def sanitize(value: str) -> str:
            return re.sub(r"[^ _a-zA-Z0-9-]", "-", str(value))

        self.css_class = self.CSS_CLASS.format(
            action=self, category=sanitize(self.category), name=sanitize(self.name)
        )

    @property
    def description(self) -> str:
        return self._get_and_call("description")

    @description.setter
    def description(self, description: str) -> None:
        self._description = description

    @property
    def icon(self) -> Icon:
        return self._get_and_call("icon")

    @icon.setter
    def icon(self, icon) -> None:
        self._icon = icon

    @property
    def endpoint(self) -> Endpoint | None:
        endpoint = self._get_and_call("endpoint")
        if endpoint is None:
            return None

        if not isinstance(endpoint, Endpoint):
            match endpoint:
                case str():
                    endpoint = self.Endpoint(endpoint)
                case tuple() | list():
                    assert len(endpoint) == 2
                    endpoint, kwargs = endpoint
                    assert isinstance(endpoint, str)
                    assert isinstance(kwargs, dict)
                    endpoint = self.Endpoint(endpoint, **kwargs)
                case _:
                    msg = f'Invalid endpoint specifier: "{endpoint!r}"'
                    raise TypeError(msg)

        return endpoint

    @endpoint.setter
    def endpoint(self, endpoint: Endpoint | None) -> None:
        self._endpoint = endpoint

    def available(self, context: dict[str, Any]) -> bool:
        """Determine if this actions is available in this `context`.

        :param context: a dict whose content is left to application needs; if
                        :attr:`.condition` is a callable it receives `context`
                        in parameter.
        """
        if not self._enabled:
            return False
        try:
            return self.pre_condition(context) and self._check_condition(context)
        except Exception:
            # Fail closed, but not silently. An action whose condition raises
            # used to disappear looking exactly like one the user is not
            # allowed -- so a broken condition stayed broken for as long as
            # nobody missed the button. Conditions are authorization; a bug in
            # one must not be indistinguishable from a denial.
            logger.exception(
                "action {name!r} in category {category!r} raised from its "
                "condition; treating it as unavailable",
                name=self.name,
                category=self.category,
            )
            return False

    def pre_condition(self, context: dict[str, Any]) -> bool:
        """Called by :meth:`.available` before checking condition.

        Subclasses may override it to ease creating actions with
        repetitive check (for example: actions that apply on a given
        content type only).
        """
        return True

    def _check_condition(self, context: dict[str, Any]) -> bool:
        if self.condition is None:
            return True

        if callable(self.condition):
            return self.condition(context)
        return bool(self.condition)

    def render(self, **kwargs: Any) -> Markup:
        if not self.template:
            self.template = Template(self.template_string)

        template = self.template

        if not isinstance(template, Template):
            template = current_app.jinja_env.get_or_select_template(template)

        params = self.get_render_args(**kwargs)
        return Markup(template.render(params))

    def get_render_args(self, **kwargs: Any) -> dict[str, Any]:
        params = {"action": self}
        params.update(actions.context)
        params.update(kwargs)
        params["csrf"] = csrf
        params["url"] = self.url(params)
        return params

    def url(self, context: dict[str, Any] | None = None) -> str:
        if callable(self._url):
            return self._url(context)

        if self.endpoint:
            return str(self.endpoint)

        return self._url


class ModalActionMixin:
    """Mixin for actions that open a modal.

    `url` names the dialog, e.g. `#modal-delete`; vite/src/modals.js opens it.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # `url` reaches the browser as a querySelector argument, so a real URL
        # here is not a broken link but a thrown SyntaxError on click. The
        # "Viewers list" action was a ModalAction pointing at a page for years,
        # and only a browser could have noticed. Reject it at import time.
        url = kwargs.get("url")
        if not isinstance(url, str) or not url.startswith("#"):
            msg = (
                f"{type(self).__name__} url must be a dialog selector "
                f'like "#modal-delete", got {url!r}'
            )
            raise ValueError(msg)

        super().__init__(*args, **kwargs)

    template_string = (
        '<button type="button" class="{{ action.css_class }}" '
        'data-modal-open="{{ url }}">'
        "{%- if action.icon %}{{ action.icon}} {% endif %}"
        "{{ action.title }}"
        "</button>"
    )


class ButtonAction(Action):
    # Tailwind button classes mapped by btn_class
    BTN_CLASSES = {
        "default": "text-gray-700 bg-white border border-gray-300 hover:bg-gray-50",
        "primary": "text-white bg-blue-600 hover:bg-blue-700",
        "success": "text-white bg-green-600 hover:bg-green-700",
        "danger": "text-white bg-red-600 hover:bg-red-700",
        "warning": "text-white bg-yellow-600 hover:bg-yellow-700",
        "info": "text-white bg-cyan-600 hover:bg-cyan-700",
    }

    template_string = (
        '<button type="submit" '
        'class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md '
        '{% if action.btn_class == "primary" %}text-white bg-blue-600 hover:bg-blue-700'
        '{% elif action.btn_class == "success" %}text-white bg-green-600 hover:bg-green-700'
        '{% elif action.btn_class == "danger" %}text-white bg-red-600 hover:bg-red-700'
        '{% elif action.btn_class == "warning" %}text-white bg-yellow-600 hover:bg-yellow-700'
        '{% elif action.btn_class == "info" %}text-white bg-cyan-600 hover:bg-cyan-700'
        "{% else %}text-gray-700 bg-white border border-gray-300 hover:bg-gray-50{% endif %}"
        ' {{ action.css_class}}" '
        'name="{{ action.submit_name }}" '
        'value="{{ action.name }}">'
        "{%- if action.icon %}{{ action.icon }} {% endif %}"
        "{{ action.title }}</button>"
    )

    btn_class = "default"

    def __init__(
        self,
        category: str,
        name: str,
        submit_name: str = "__action",
        btn_class: str = "default",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(category, name, *args, **kwargs)
        self.submit_name = submit_name
        self.btn_class = btn_class


class ActionGroup(Action):
    """A group of single actions."""

    template_string = (
        '<div class="inline-flex rounded-md shadow-sm" role="group" aria-label="{{ action.name}}">'
        "{%- for entry in action_items %}"
        "{{ entry.render() }}"
        "{%- endfor %}"
        "</div>"
    )

    def __init__(self, category, name, items=(), *args, **kwargs) -> None:
        super().__init__(category, name, *args, **kwargs)
        self.items = list(items)

    def get_render_args(self, **kwargs):
        params = super().get_render_args(**kwargs)
        params["action_items"] = [a for a in self.items if a.available(params)]
        return params


class ActionGroupItem(Action):
    #: if True, add a divider in dropdowns
    divider = False

    def __init__(self, category, name, divider=False, *args, **kwargs) -> None:
        super().__init__(category, name, *args, **kwargs)
        self.divider = divider


class ActionRegistry:
    """The Action registry.

    This is a Flask extension which registers :class:`.Action` sets. Actions are
    grouped by category and are ordered by registering order.

    From your application use the instanciated registry :data:`.actions`.

    The registry is available in jinja2 templates as `actions`.
    """

    __EXTENSION_NAME = "abilian:actions"

    def init_app(self, app: Flask) -> None:
        if self.__EXTENSION_NAME in app.extensions:
            logger.warning(
                "ActionRegistry.init_app: actions already enabled on this application"
            )
            return

        app.extensions[self.__EXTENSION_NAME] = {"categories": {}}
        appcontext_pushed.connect(self._init_context, app)

        @app.context_processor
        def add_registry_to_jinja_context() -> dict[str, ActionRegistry]:
            return {"actions": self}

    def installed(self, app: Flask | None = None) -> bool:
        """Return `True` if the registry has been installed in current
        applications."""
        if app is None:
            app = current_app
        return self.__EXTENSION_NAME in app.extensions

    def clear(self) -> None:
        """Remove all registered actions."""
        self._state["categories"] = {}

    def register(self, *actions: Any) -> None:
        """Register `actions` in the current application. All `actions` must be
        an instance of :class:`.Action` or one of its subclasses.

        If `overwrite` is `True`, then it is allowed to overwrite an
        existing action with same name and category; else `ValueError`
        is raised.
        """
        assert self.installed(), "Actions not enabled on this application"
        assert all(isinstance(a, Action) for a in actions)

        for action in actions:
            cat = action.category
            reg = self._state["categories"].setdefault(cat, [])
            reg.append(action)

    def actions(self, context: Any | None = None) -> dict[str, Any]:
        """Return a mapping of category => actions list.

        Actions are filtered according to :meth:`.Action.available`.

        if `context` is None, then current action context is used
        (:attr:`context`).
        """
        assert self.installed(), "Actions not enabled on this application"
        result = {}
        if context is None:
            context = self.context

        for cat, actions in self._state["categories"].items():
            result[cat] = [a for a in actions if a.available(context)]
        return result

    def for_category(self, category: str, context: Any = None) -> list[Action]:
        """Returns actions list for this category in current application.

        Actions are filtered according to :meth:`.Action.available`.

        if `context` is None, then current action context is used
        (:attr:`context`)
        """
        assert self.installed(), "Actions not enabled on this application"
        actions = self._state["categories"].get(category, [])

        if context is None:
            context = self.context

        return [a for a in actions if a.available(context)]

    @property
    def _state(self) -> Any:
        return current_app.extensions[self.__EXTENSION_NAME]

    @staticmethod
    def _init_context(sender: Flask) -> None:
        g.action_context = {}

    @property
    def context(self) -> dict[str, bool]:
        """Return action context (dict type).

        Applications can modify it to suit their needs.
        """
        return g.action_context


actions = ActionRegistry()
