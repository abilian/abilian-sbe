# Copyright (c) 2012-2024, Abilian SAS

"""The build hook that compiles the translations."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

HOOK = Path(__file__).parents[2] / "hatch_build.py"

BROKEN_PO = """\
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

#, python-format
msgid "Hello %(name)s"
msgstr "Bonjour %(nom)s"
"""


@pytest.fixture
def hatch_build(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The hook module; hatchling exists only in the build environment."""
    interface = types.SimpleNamespace(BuildHookInterface=object)
    monkeypatch.setitem(
        sys.modules, "hatchling.builders.hooks.plugin.interface", interface
    )
    spec = importlib.util.spec_from_file_location("hatch_build", HOOK)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_catalog_that_does_not_compile_fails_the_build(
    hatch_build: ModuleType, tmp_path: Path
) -> None:
    """Babel's errors were ignored: the package shipped without the catalog."""
    for directory in hatch_build.TRANSLATIONS:
        messages = tmp_path / directory / "fr" / "LC_MESSAGES"
        messages.mkdir(parents=True)
        (messages / "messages.po").write_text(BROKEN_PO)

    with pytest.raises(RuntimeError, match="translations"):
        hatch_build.compile_translations(tmp_path)
