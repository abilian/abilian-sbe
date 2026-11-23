# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any

from attrs import mutable
from flask import current_app
from loguru import logger

from abilian.core.util import fqcn

if TYPE_CHECKING:
    from collections.abc import Callable

    from abilian.app import Application


class ServiceNotRegisteredError(Exception):
    pass


@mutable
class ServiceState:
    """Service state stored in Application.extensions."""

    service: Service
    running: bool = False


class Service:
    """Base class for services."""

    #: State class to use for this Service
    AppStateClass = ServiceState

    #: service name in Application.extensions / Application.services
    name = ""

    def __init__(self, app: Any | None = None) -> None:
        if not self.name:
            msg = f"Service must have a name ({fqcn(self.__class__)})"
            raise ValueError(msg)

        self.logger = logger
        if app:
            self.init_app(app)

    def init_app(self, app: Application) -> None:
        app.extensions[self.name] = self.AppStateClass(self)
        app.service_manager.add_service(self.name, self)

    def start(self, ignore_state: bool = False) -> None:
        """Starts the service."""
        self._toggle_running(True, ignore_state)

    def stop(self, ignore_state: bool = False) -> None:
        """Stops the service."""
        self._toggle_running(False, ignore_state)

    def _toggle_running(self, run_state: bool, ignore_state: bool = False) -> None:
        state = self.app_state
        run_state = bool(run_state)
        if not ignore_state:
            assert run_state ^ state.running
        state.running = run_state

    @property
    def app_state(self) -> Any:
        """Current service state in current application.

        :raise:RuntimeError if working outside application context.
        """
        try:
            return current_app.extensions[self.name]
        except KeyError as e:
            raise ServiceNotRegisteredError(self.name) from e

    @property
    def running(self) -> bool:
        """
        :returns: `False` if working outside application context, if service is
            not registered on current application, or if service is halted
            for current application.
        """
        try:
            return self.app_state.running
        except (RuntimeError, ServiceNotRegisteredError):
            # RuntimeError: happens when current_app is None: working outside
            # application context
            return False

    @staticmethod
    def if_running(meth: Callable) -> Callable:
        """Decorator for service methods that must be ran only if service is in
        running state."""

        @wraps(meth)
        def check_running(self: Any, *args: Any, **kwargs: Any) -> Any | None:
            if not self.running:
                return None
            return meth(self, *args, **kwargs)

        return check_running
