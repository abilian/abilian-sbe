# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Blueprint, Flask, g
from loguru import logger
from werkzeug.exceptions import Forbidden
from werkzeug.utils import import_string

from abilian.core.extensions.login import AnonymousUser, current_user
from abilian.core.util import unwrap
from abilian.i18n import _l
from abilian.services.security import ADMIN, is_site_admin, security
from abilian.web.action import Endpoint, actions
from abilian.web.nav import BreadcrumbItem, NavGroup, NavItem

from .panel import AdminPanel

if TYPE_CHECKING:
    from collections.abc import Callable

_BP_PREFIX = "admin"


class Admin:
    """Flask extension for an admin interface with pluggable admin panels.

    Note: this is quite different that a Django-style admin interface.
    """

    def __init__(self, *panels: Any, **kwargs: Any) -> None:
        self.app = None
        self.panels: list[AdminPanel] = []
        self._panels_endpoints: dict[str, AdminPanel] = {}
        self.nav_paths: dict[str, str] = {}
        self.breadcrumb_items: dict[AdminPanel, BreadcrumbItem] = {}
        self.setup_blueprint()

        def condition(context: dict[str, bool]) -> bool:
            return not current_user.is_anonymous and security.has_role(
                current_user, ADMIN
            )

        # Not rendered as a menu: the navbar reaches the admin section through
        # one entry in the user menu. This stays the container that owns the
        # panel items, the breadcrumb root and the active-path lookup.
        self.nav_root = NavGroup(
            "admin", "root", title=_l("Admin"), endpoint=None, condition=condition
        )

        for panel in panels:
            self.register_panel(panel)

        app = kwargs.pop("app", None)
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        panels = app.config.get("ADMIN_PANELS", ())

        # resolve fully qualified name into an AdminPanel object
        for fqn in panels:
            panel_class = import_string(fqn, silent=True)
            if panel_class is None:
                logger.warning('Could not import panel: "{fqn}"', fqn=fqn)
                continue
            if not issubclass(panel_class, AdminPanel):
                logger.error(
                    '"{fqn}" is not a {module}.AdminPanel, skipping',
                    fqn=fqn,
                    module=AdminPanel.__module__,
                )
                continue

            self.register_panel(panel_class())

        if not self.panels:

            @self.blueprint.route("", endpoint="no_panel")
            def no_panels_view() -> str:
                return "No panels registered"

            self.nav_root.endpoint = "admin.no_panel"
        else:
            self.nav_root.endpoint = self.nav_root.items[0].endpoint

        self.root_breadcrumb_item = BreadcrumbItem(
            label=self.nav_root.title, url=self.nav_root.endpoint
        )

        app.register_blueprint(self.blueprint)

        with app.app_context():
            actions.register(self.nav_root, *self.nav_root.items)

        self.app = app
        app.extensions["admin"] = self

    def register_panel(self, panel: Any) -> None:
        if self.app:
            msg = "Admin extension already initialized for app, cannot add more panel"
            raise ValueError(msg)

        self.panels.append(panel)
        panel.admin = self
        rule = f"/{panel.id}"
        endpoint = nav_id = panel.id
        abs_endpoint = f"admin.{endpoint}"

        if hasattr(panel, "get"):
            self.blueprint.add_url_rule(rule, endpoint, panel.get)
            self._panels_endpoints[abs_endpoint] = panel
        if hasattr(panel, "post"):
            post_endpoint = f"{endpoint}_post"
            self.blueprint.add_url_rule(
                rule, post_endpoint, panel.post, methods=["POST"]
            )
            self._panels_endpoints[f"admin.{post_endpoint}"] = panel

        panel.install_additional_rules(
            self.get_panel_url_rule_adder(panel, rule, endpoint)
        )

        nav = NavItem(
            "admin:panel",
            nav_id,
            title=panel.label,
            icon=panel.icon,
            endpoint=abs_endpoint,
        )
        self.nav_root.append(nav)
        self.nav_paths[abs_endpoint] = nav.path
        self.breadcrumb_items[panel] = BreadcrumbItem(
            label=panel.label, icon=panel.icon, url=Endpoint(abs_endpoint)
        )

    def get_panel_url_rule_adder(
        self, panel: Any, base_url: str, base_endpoint: str
    ) -> Callable:
        extension = self

        def add_url_rule(
            rule: str,
            endpoint: Any | None = None,
            view_func: Callable | None = None,
            **kwargs: Any,
        ) -> None:
            if not rule:
                # '' is already used for panel get/post
                msg = f"Invalid additional url rule: {rule!r}"
                raise ValueError(msg)

            if endpoint is None:
                endpoint = view_func.__name__

            if not endpoint.startswith(base_endpoint):
                endpoint = f"{base_endpoint}_{endpoint}"

            extension._panels_endpoints[f"admin.{endpoint}"] = panel
            self.blueprint.add_url_rule(
                base_url + rule, endpoint=endpoint, view_func=view_func, **kwargs
            )

        return add_url_rule

    def setup_blueprint(self) -> None:
        self.blueprint = Blueprint(
            "admin", __name__, template_folder="templates", url_prefix=f"/{_BP_PREFIX}"
        )

        # Checked before the panels read the URL: a panel looks up what it
        # names, and its 404 would tell anyone what exists.
        self.blueprint.url_value_preprocessor(check_security)
        self.blueprint.url_value_preprocessor(self.build_breadcrumbs)
        self.blueprint.url_value_preprocessor(self.panel_preprocess_value)

    def panel_preprocess_value(self, endpoint: str, view_args: dict[Any, Any]) -> None:
        panel = self._panels_endpoints.get(endpoint)
        if panel is not None:
            panel.url_value_preprocess(endpoint, view_args)

    def build_breadcrumbs(self, endpoint: str, view_args: dict[Any, Any]) -> None:
        g.breadcrumb.append(self.root_breadcrumb_item)
        g.nav["active"] = self.nav_paths.get(endpoint, self.nav_root.path)
        panel = self._panels_endpoints.get(endpoint)
        if panel:
            endpoint_bc = self.breadcrumb_items.get(panel)
            if endpoint_bc:
                g.breadcrumb.append(endpoint_bc)


def check_security(endpoint: str | None, view_args: dict[str, Any] | None) -> None:
    """Refuse anyone but a site administrator.

    Runs before flask-login has loaded the visitor into `g.user`, so it reads
    the visitor itself instead of letting `is_site_admin` look there.
    """
    user = unwrap(current_user)
    if isinstance(user, AnonymousUser) or not is_site_admin(user):
        raise Forbidden
