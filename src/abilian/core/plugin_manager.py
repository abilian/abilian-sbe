# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from attrs import field, frozen

if TYPE_CHECKING:
    from flask import Flask

CORE_PLUGINS = [
    "abilian.web.search",
    "abilian.web.tags",
    "abilian.web.comments",
    "abilian.web.uploads",
    "abilian.web.attachments",
]


@frozen
class PluginManager:
    """Mixin that provides support for loading plugins."""

    app: Flask
    registered_plugins: set[str] = field(factory=set)

    def register_plugins(self, plugins: list[str]) -> None:
        """Load plugins listed in config variable 'PLUGINS'."""
        for plugin_fqdn in plugins:
            if plugin_fqdn not in self.registered_plugins:
                self._register_plugin(plugin_fqdn)
                self.registered_plugins.add(plugin_fqdn)

    def _register_plugin(self, name: str) -> None:
        """Load and register a plugin given its package name."""
        module = importlib.import_module(name)
        module.register_plugin(self.app)  # type: ignore
