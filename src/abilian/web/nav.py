# Copyright (c) 2012-2024, Abilian SAS

"""Navigation elements.

Abilian define theses categories:   `section`:     Used for navigation
elements relevant to site section   `user`:     User for element that
should appear in user menu
"""

from __future__ import annotations

import typing
from typing import Any

from flask import Flask, g, request
from jinja2 import Template
from markupsafe import Markup

from abilian.i18n import _l

from .action import ACTIVE, ENABLED, Action, Glyphicon, getset

if typing.TYPE_CHECKING:
    from abilian.web.action import Endpoint, Status


def setup_nav_and_breadcrumbs(_app: Flask) -> None:
    """Listener for `request_started` event.

    If you want to customize first items of breadcrumbs, override
    :meth:`init_breadcrumbs`
    """
    g.nav = {"active": None}  # active section
    g.breadcrumb = []
    init_breadcrumbs()


def init_breadcrumbs() -> None:
    """Insert the first element in breadcrumbs.

    This happens during `request_started` event, which is triggered
    before any url_value_preprocessor and `before_request` handlers.
    """
    g.breadcrumb.append(
        BreadcrumbItem(
            icon="home", url=f"/{request.script_root}", description=_l("Home")
        )
    )


class NavItem(Action):
    """A single navigation item."""

    divider = False

    def __init__(
        self, category: str, name: str, divider: bool = False, *args: Any, **kwargs: Any
    ) -> None:
        category = f"navigation:{category}"
        super().__init__(category, name, *args, **kwargs)
        self.divider = divider

    @getset
    def status(self, value: Any | None = None) -> Status:
        current = g.nav.get("active")
        if current is None:
            return ENABLED

        if not current.startswith("navigation:"):
            current = f"navigation:{current}"

        status = ACTIVE if current == self.path else ENABLED
        return status

    @property
    def path(self) -> str:
        return f"{self.category}:{self.name}"


class NavGroup(NavItem):
    """A navigation group: a disclosure, its items in a list."""

    template_string = """
    <details class="{{ action.css_class }}">
      {#- The icon speaks for the group when there is one (the user menu's avatar);
          the title stays as its accessible name, the avatar's alt being empty. #}
      <summary>
        {%- if action.icon %}{{ action.icon }}<span class="sbe-sr-only">{{ action.title }}</span>
        {%- else %}{{ action.title }}{%- endif %}
      </summary>
      <ul class="nav-menu">
        {%- for item in action_items %}
        <li{% if item.status == 'active' %} aria-current="page"{% endif %}>{{ item.render() }}</li>
        {%- endfor %}
      </ul>
    </details>
    """

    def __init__(
        self, category: str, name: str, items: tuple[NavItem] = (), *args, **kwargs
    ) -> None:
        super().__init__(category, name, *args, **kwargs)
        self.items = list(items)
        self._paths = {self.path}
        for i in self.items:
            self._paths.add(i.path)

    def append(self, item: NavItem) -> None:
        self.items.append(item)
        self._paths.add(item.path)

    def insert(self, pos: int, item: NavItem) -> None:
        self.items.insert(pos, item)
        self._paths.add(item.path)

    def get_render_args(self, **kwargs: Any) -> dict[str, Any]:
        params = super().get_render_args(**kwargs)
        params["action_items"] = [a for a in self.items if a.available(params)]
        return params

    @getset
    def status(self, value: Any | None = None) -> Status:
        current = g.nav.get("active")
        if current is None:
            return ENABLED

        if not current.startswith("navigation:"):
            current = f"navigation:{current}"
        status = ACTIVE if current in self._paths else ENABLED
        return status


class BreadcrumbItem:
    """A breadcrumb element has at least a label or an icon."""

    #: Label shown to user. May be an i18n string instance
    label = None

    #: Icon to use.
    icon = None

    #: Additional text, can be used as tooltip for example
    description = None

    #: either an Unicode string or an :class:`Endpoint` instance.
    _url = None

    template_string = (
        '{%- if url %}<a href="{{ url }}"'
        "{%- if item.description and not item.label %}"
        ' aria-label="{{ item.description | e }}"{% endif %}>{%- endif %}'
        "{%- if item.icon %}{{ item.icon }}\u00a0{%- endif %}"
        "{{ item.label }}"
        "{%- if url %}</a>{%- endif %}"
    )

    def __init__(
        self,
        label: str = "",
        url: str | Endpoint = "#",
        icon: str | None = None,
        description: Any | None = None,
    ) -> None:
        # don't test 'label or...': if label is a lazy_gettext, it will be
        # resolved. If this item is created in a url_value_preprocessor, it will
        # setup i18n before auth has loaded user, so i18n will fallback on browser
        # negociation instead of user's site preference, and load wrong catalogs for
        # the whole request.
        assert label is not None or icon is None
        self.label = label
        if isinstance(icon, str):
            icon = Glyphicon(icon)

        self.icon = icon
        self.description = description
        self._url = url
        self.__template = Template(self.template_string)

    @property
    def url(self) -> str:
        return str(self._url)

    def render(self) -> Markup:
        return Markup(self.__template.render(item=self, url=self.url))
