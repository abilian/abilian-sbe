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
    """A navigation group renders a list of items using Alpine.js."""

    template_string = """
    <div x-data="{ open: false }" class="relative {{ action.css_class }}" @keydown.escape="open = false">
      <button type="button" @click="open = !open" aria-haspopup="true" :aria-expanded="open"
              class="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium
                     text-current opacity-90 hover:opacity-100">
        {#- The icon speaks for the group when there is one: the user menu shows
            the avatar, which needs neither the name nor a chevron to read as a
            menu. The title stays as the button's accessible name -- the avatar's
            alt is empty, so dropping it outright would leave the menu unnamed
            for a screen reader. A group with no icon has only its
            label, so it keeps the chevron to show there is more behind it. #}
        {%- if action.icon %}
          {{ action.icon }}<span class="sr-only">{{ action.title }}</span>
        {%- else %}
          {{ action.title }}
          <svg class="ml-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        {%- endif %}
      </button>
      <ul x-show="open" @click.away="open = false" x-transition
          class="nav-menu absolute right-0 z-10 mt-2 w-48 origin-top-right rounded-md
                 bg-white text-gray-700 shadow-lg ring-1 ring-black/5 py-1">
        {%- for item in action_items %}
        {%- if item.divider %}<li class="border-t border-gray-100 my-1"></li>{%- endif %}
        <li class="px-4 py-2 hover:bg-gray-100 {% if item.status == 'active' %}bg-gray-100{% endif %}">{{ item.render() }}</li>
        {%- endfor %}
      </ul>
    </div>
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
