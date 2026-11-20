# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock, Timeout

from .exceptions import ConversionError

if TYPE_CHECKING:
    from collections.abc import Callable

LOCK_EXPIRE = 1800  # 30 min, in case many request in //
LOCK_FILES = {}

#: Set by init_conversion_lock_dir(). A single slot, not a list: it used to be
#: appended to, so a second app in the same process grew the list while every
#: lock kept pointing at the first app's instance path.
_lock_dir: Path | None = None


def init_conversion_lock_dir(instance_path: str) -> None:
    global _lock_dir  # noqa: PLW0603

    _lock_dir = Path(instance_path) / "lock"
    _lock_dir.mkdir(parents=True, exist_ok=True)
    # Cached locks belong to the previous directory.
    LOCK_FILES.clear()


def get_lock_file(name: str) -> FileLock:
    if _lock_dir is None:
        msg = (
            "Conversion lock directory is not configured. "
            "ConversionService.init_app() does this; outside an application, "
            "call init_conversion_lock_dir() first."
        )
        raise RuntimeError(msg)

    if lock := LOCK_FILES.get(name):
        return lock
    lock = FileLock(_lock_dir / f"{name}.lock", timeout=LOCK_EXPIRE)
    LOCK_FILES[name] = lock
    return lock


def acquire_lock(name: str) -> Callable:
    """Ensure the decorated function is alone to run by using a lock file."""

    def locked(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            lock = get_lock_file(name)
            try:
                lock.acquire()
                return func(*args, **kwargs)
            except Timeout as e:
                raise ConversionError from e
            finally:
                lock.release()

        return wrapper

    return locked
