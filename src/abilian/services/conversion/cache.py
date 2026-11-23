# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.core.util import atomic_write

if TYPE_CHECKING:
    from pathlib import Path

CacheKey = tuple[str, str]


class Cache:
    cache_dir: Path

    def _path(self, key: CacheKey) -> Path:
        """File path for `key`:"""
        type = key[0]
        uuid = key[1]
        return self.cache_dir / type / f"{uuid}.blob"

    def __contains__(self, key: CacheKey) -> bool:
        return self._path(key).exists()

    def get(self, key: CacheKey) -> str | bytes | None:
        if key[0] == "txt":
            return self.get_text(key)
        return self.get_bytes(key)

    __getitem__ = get

    def get_bytes(self, key: CacheKey) -> bytes | None:
        if key in self:
            path = self._path(key)
            return path.read_bytes()
        return None

    def get_text(self, key: CacheKey) -> str | None:
        if key in self:
            path = self._path(key)
            return path.read_text("utf8")
        return None

    def set(self, key: CacheKey, value: str | bytes) -> None:
        """Store `value`, atomically.

        `__contains__` only checks the file exists, so a reader must never
        see a half-written one.
        """
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if key[0] == "txt":
            assert isinstance(value, str)
            data = value.encode("utf8")
        else:
            assert isinstance(value, bytes)
            data = value
        atomic_write(path, data)

    __setitem__ = set
