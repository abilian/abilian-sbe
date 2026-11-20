# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from abilian.core.extensions import db
from abilian.services import Service

from .models import Setting

if TYPE_CHECKING:
    from collections.abc import Iterator


class SettingsNamespace:
    """Allow to query :class:`SettingsService` service within a namespace.

    Basically it prefixes keys with namespace name and a colon.
    """

    def __init__(self, name: str, service: SettingsService) -> None:
        self.name = name
        self.service = service

    def namespace(self, name: str) -> SettingsNamespace:
        """A namespace within this namespace."""
        return SettingsNamespace(self.ns(name), self.service)

    def ns(self, key: str) -> str:
        """Returns full key name for use in settings service."""
        return f"{self.name}:{key}"

    def keys(self, prefix: str = "") -> list[str]:
        prefix = f"{self.name}:{prefix}"
        start = len(self.name) + 1  # +1 for colon
        return [k[start:] for k in self.service.keys(prefix=prefix)]

    def iteritems(self, prefix: str = "") -> Iterator[tuple[str, int]]:
        prefix = f"{self.name}:{prefix}"
        start = len(self.name) + 1  # +1 for colon
        for k, v in self.service.iteritems(prefix=prefix):
            yield (k[start:], v)

    def as_dict(self, prefix: str = "") -> dict[str, int]:
        return dict(self.iteritems(prefix))

    def get(self, key: str) -> int:
        """Proxy to :meth:`SettingsService.get`"""
        return self.service.get(self.ns(key))

    def set(self, key: str, *args, **kwargs):
        return self.service.set(self.ns(key), *args, **kwargs)

    def delete(self, key: str, silent: bool = True) -> Any | None:
        return self.service.delete(self.ns(key), silent=silent)


class SettingsService(Service):
    name = "settings"

    def namespace(self, name: str) -> SettingsNamespace:
        return SettingsNamespace(name, self)

    def keys(self, prefix: str | None = None) -> list[str]:
        """List all keys, with optional prefix filtering."""
        query = Setting.query
        if prefix:
            query = query.filter(Setting.key.startswith(prefix))

        # don't use iteritems: 'value' require little processing whereas we only
        # want 'key'
        return [i[0] for i in query.yield_per(1000).with_entities(Setting.key)]

    def iteritems(self, prefix: str | None = None) -> Iterator[tuple[str, Any]]:
        """Like dict.iteritems."""
        query = Setting.query
        if prefix:
            query = query.filter(Setting.key.startswith(prefix))

        for s in query.yield_per(1000):
            yield (s.key, s.value)

    items = iteritems

    def as_dict(self, prefix: str | None = None) -> dict[str, Any]:
        """Return a mapping key -> value of settings, with optional prefix
        filtering."""
        return dict(self.iteritems(prefix))

    def _get_setting(self, key: str) -> Setting:
        s = Setting.query.get(key)
        if s is None:
            raise KeyError(key)

        return s

    def get(self, key: str) -> Any:
        """Returns value of a previously stored key."""
        s = self._get_setting(key)
        return s.value

    def set(self, key: str, value: Any, type_: str | None = None) -> None:
        try:
            s = self._get_setting(key)
        except KeyError as e:
            if not type_:
                msg = "tried to set a new key without specifiying its type"
                raise ValueError(msg) from e
            s = Setting(key=key, type=type_)

        # Always add to session. This covers the case delete(key);set(key).
        # Without it, Setting would still be in session 'delete' queue.
        db.session.add(s)
        s.value = value

    def delete(self, key: str, silent: bool = True) -> None:
        try:
            s = self._get_setting(key)
        except KeyError:
            if not silent:
                raise
        else:
            db.session.delete(s)
