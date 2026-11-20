# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from flask import current_app
from flask_debugtoolbar.panels import DebugPanel

from abilian.core.entities import Entity
from abilian.core.models.subjects import Group
from abilian.i18n import _
from abilian.services import get_service
from abilian.web.action import actions

from .models import ANONYMOUS


class SecurityInfoDebugPanel(DebugPanel):
    """A panel to display current roles and permissions for "current"
    object."""

    name = "SecurityInfo"

    @property
    def current_obj(self):
        return actions.context.get("object")

    @property
    def has_content(self):
        obj = self.current_obj
        return obj is not None and isinstance(obj, Entity) and obj.id is not None

    def nav_title(self):
        return _("Security Info")

    def nav_subtitle(self):
        """Subtitle showing until title in toolbar."""
        obj = self.current_obj
        if not obj:
            return _("No current object")

        try:
            return f"{obj.__class__.__name__}(id={obj.id})"
        except Exception:
            return ""

    def title(self):
        return self.nav_title()

    def url(self) -> str:
        return ""

    def content(self):
        obj = self.current_obj
        security = get_service("security")
        context = self.context.copy()

        context["permissions"] = security.get_permissions_assignments(obj=obj)
        context["roles"] = roles = {}

        for principal, r in security.get_role_assignements(obj=obj):
            if r not in roles:
                roles[r] = {"anonymous": False, "users": set(), "groups": set()}

            info = roles[r]
            if principal is ANONYMOUS:
                info["anonymous"] = True
            elif isinstance(principal, Group):
                info["groups"].add(principal)
            else:
                info["users"].add(principal)

        for info in roles.values():
            info["groups"] = [
                f"{g} (id={g.id})" for g in sorted(info["groups"], key=lambda g: g.name)
            ]
            users = sorted(
                info["users"], key=lambda u: (u.last_name.lower(), u.first_name.lower())
            )
            info["users"] = [f'{u} (id={u.id}, email="{u.email}")' for u in users]

        jinja_env = current_app.jinja_env
        jinja_env.filters.update(self.jinja_env.filters)
        template = jinja_env.get_or_select_template(
            "debug_panels/security_info_panel.html"
        )

        return template.render(context)
