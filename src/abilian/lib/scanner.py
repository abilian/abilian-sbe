from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def scan_packages(package_names: Iterable[str]) -> None:
    """Scan all packages from the given list."""
    assert not isinstance(package_names, str)

    for package_name in package_names:
        scan_package(package_name)


def scan_package(package_name: str) -> None:
    """Import all modules in a package (recursively), for side effects."""
    assert isinstance(package_name, str)

    for module_name in _iter_module_names(package_name):
        importlib.import_module(module_name)


def _iter_module_names(package_name: str):
    package_or_module = importlib.import_module(package_name)
    if not hasattr(package_or_module, "__path__"):
        # module, not package
        return

    path = package_or_module.__path__
    prefix = package_or_module.__name__ + "."
    for _, module_name, _ in pkgutil.walk_packages(path, prefix):
        yield module_name
