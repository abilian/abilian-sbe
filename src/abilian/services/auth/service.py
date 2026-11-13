# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from flask import Flask, current_app, g, redirect, request, url_for
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_user, user_logged_in, user_logged_out
from loguru import logger
from werkzeug.exceptions import Forbidden

from abilian.core.extensions import db, login_manager
from abilian.core.models.subjects import User
from abilian.core.signals import user_loaded
from abilian.core.util import unwrap
from abilian.services import Service, ServiceState, get_service
from abilian.web.action import DynamicIcon, Endpoint, actions
from abilian.web.nav import NavGroup, NavItem

from .models import LoginSession
from .views import login as login_views

if TYPE_CHECKING:
    from collections.abc import Callable

    from werkzeug.wrappers import Response

    from abilian.app import Application

__all__ = ["AuthService", "user_menu"]


def is_anonymous(context: dict[str, bool]) -> bool:
    return current_user.is_anonymous


def is_authenticated(context: dict[str, bool]) -> bool:
    return not is_anonymous(context)


def _user_photo_endpoint() -> str:
    from abilian.web.views import images  # lazy import: avoid circular import

    return images.user_url_args(current_user, 16)[0]


def _user_photo_icon_args(icon: DynamicIcon, url_args: dict) -> dict[str, Any]:
    from abilian.web.views import images  # lazy import avoid circular import

    return images.user_url_args(current_user, max(icon.width, icon.height))[1]


def is_admin(context: dict[str, bool]) -> bool:
    from abilian.services.security import is_site_admin  # lazy: circular import

    if "admin" not in current_app.extensions:
        return False
    return is_authenticated(context) and is_site_admin()


def _admin_endpoint(context: dict[str, bool]) -> Endpoint:
    """The admin landing page, which is whichever panel registered first.

    Resolved per request rather than at import: the endpoint depends on which
    panels the app configured, and one process can serve several apps.
    """
    return current_app.extensions["admin"].nav_root.endpoint


user_menu = NavGroup(
    "user",
    "authenticated",
    title=lambda c: current_user.name,
    icon=DynamicIcon(
        endpoint=_user_photo_endpoint,
        css="avatar",
        # Matches `nav .avatar` in vite/src/components/navbar.css; the value
        # also picks the resolution the photo is fetched at.
        size=36,
        url_args=_user_photo_icon_args,
    ),
    condition=is_authenticated,
    items=(
        # The admin section used to be a second dropdown of its own in the top
        # bar, holding nothing but the panel list the admin pages already show
        # in their own sidebar. One entry here reaches the same place.
        NavItem(
            "user",
            "admin",
            title=_l("Admin"),
            icon="wrench",
            endpoint=_admin_endpoint,
            condition=is_admin,
        ),
        NavItem(
            "user",
            "logout",
            title=_l("Logout"),
            icon="sign-out",
            url=lambda context: url_for("login.logout"),
            divider=True,
        ),
    ),
)

_ACTIONS = (
    NavItem(
        "user",
        "login",
        title=_l("Login"),
        icon="sign-in",
        url=lambda context: url_for("login.login_form"),
        condition=is_anonymous,
    ),
    user_menu,
)


class AuthServiceState(ServiceState):
    """State class for :class:`AuthService`"""

    bp_access_controllers: dict[str | None, list[Callable]]
    endpoint_access_controllers: dict[str, list[Callable]]

    def __init__(self, service: AuthService, *args: Any, **kwargs: Any) -> None:
        super().__init__(service, *args, **kwargs)
        self.bp_access_controllers = {None: []}
        self.endpoint_access_controllers = {}

    def add_bp_access_controller(self, blueprint: str, func: Callable) -> None:
        self.bp_access_controllers.setdefault(blueprint, []).append(func)

    def add_endpoint_access_controller(self, endpoint: str, func: Callable) -> None:
        self.endpoint_access_controllers.setdefault(endpoint, []).append(func)


class AuthService(Service):
    name = "auth"
    AppStateClass = AuthServiceState
    login_url_prefix: str

    def init_app(self, app: Flask) -> None:
        login_manager.init_app(app)
        login_manager.login_view = "login.login_form"

        super().init_app(app)

        self.login_url_prefix = app.config.get("LOGIN_URL", "/user")

        app.before_request(self.do_access_control)
        app.before_request(self.update_user_session_data)
        user_logged_in.connect(self.user_logged_in, sender=app)
        user_logged_out.connect(self.user_logged_out, sender=app)

        app.register_blueprint(login_views, url_prefix=self.login_url_prefix)

        with app.app_context():
            actions.register(*_ACTIONS)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            user = User.query.get(user_id)

            if not user or not user.can_login:
                # if a user is edited and should not have access any more, this
                # will ensure they cannot continue if he had an active session
                return None
        except Exception:
            logger.opt(exception=True).warning("Error during login.")
            session = db.session()
            if not session.is_active:
                # session is not usable, rollback should restore a usable
                # session
                session.rollback()

            return None

        app = unwrap(current_app)
        auth_service = cast("AuthService", get_service(AuthService.name))
        auth_service.user_logged_in(app, user)
        user_loaded.send(app, user=user)
        return user

    def user_logged_in(self, app: Application, user: User) -> None:
        # `g.user` is used as `current_user`, but `current_user` is actually looking
        # for `request.user` whereas `g` is on app local stack.
        #
        # `g.logged_user` is the actual user. In the future for example we may allow
        # a manager to see site as another user (impersonate), or propose a "see as
        # anonymous" function

        g.user = g.logged_user = user

    def user_logged_out(self, app: Application, user: User) -> None:
        if hasattr(g, "user"):
            del g.user
            del g.logged_user

    def redirect_to_login(self, next_url=True) -> Response:
        kw = {}
        if next_url is not False:
            kw["next"] = request.url if next_url is True else next_url

        return redirect(url_for(login_manager.login_view, **kw))

    def do_access_control(self) -> Response | None:
        """`before_request` handler to check if user should be redirected to
        login page."""
        from abilian.services import security_service

        if current_app.testing and current_app.config.get("NO_LOGIN"):
            # Special case for tests
            user = User.query.get(0)
            login_user(user, force=True)
            return None

        state = self.app_state
        user = unwrap(current_user)

        # Another special case for tests
        if current_app.testing and getattr(user, "is_admin", False):
            return None

        user_roles = frozenset(security_service.get_roles(user))
        endpoint = request.endpoint
        blueprint = request.blueprint

        access_controllers: list[Callable] = []
        access_controllers.extend(state.bp_access_controllers.get(None, []))

        if blueprint and blueprint in state.bp_access_controllers:
            access_controllers.extend(state.bp_access_controllers[blueprint])

        if endpoint and endpoint in state.endpoint_access_controllers:
            access_controllers.extend(state.endpoint_access_controllers[endpoint])

        for access_controller in reversed(access_controllers):
            verdict = access_controller(user=user, roles=user_roles)
            match verdict:
                case None:
                    continue

                case True:
                    return None
            if user.is_anonymous:
                return self.redirect_to_login()
            raise Forbidden

        # default policy
        if current_app.config.get("PRIVATE_SITE") and user.is_anonymous:
            return self.redirect_to_login()

        return None

    def update_user_session_data(self) -> None:
        user = current_user
        if current_user.is_anonymous:
            return

        # Update last_active every 60 seconds only so as to not stress
        # the database too much.
        now = datetime.utcnow()
        if user.last_active is None or (now - user.last_active) > timedelta(minutes=1):
            user.last_active = now
            db.session.add(user)
            db.session.commit()

        refresh_login_session(user)


def refresh_login_session(user: User) -> None:
    now = datetime.utcnow()
    session = LoginSession.query.get_active_for(user)
    if not session:
        return

    from_now = now - session.last_active_at

    if from_now > timedelta(hours=1):
        session.ended_at = session.last_active_at
        session = LoginSession.new()
        db.session.add(session)
        db.session.commit()

    elif from_now > timedelta(minutes=1):
        session.last_active_at = now
        db.session.commit()
