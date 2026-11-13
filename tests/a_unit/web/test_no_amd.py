# Copyright (c) 2012-2024, Abilian SAS

"""The AMD shim is gone, so a `require([...])` left behind is a page script that
throws, and only on the page that has it."""

from __future__ import annotations

import re
from pathlib import Path

import abilian

ROOT = Path(abilian.__file__).parent
AMD_CALL = re.compile(r"(?<![.\w])(?:require\(\s*\[|define\(\s*[\"'\[])")
VENDORED = {"pdfjs", "vite"}


def test_nothing_calls_require_or_define() -> None:
    sources = (*ROOT.rglob("*.html"), *ROOT.rglob("*.js"))
    offenders = [
        str(path.relative_to(ROOT))
        for path in sources
        if not VENDORED.intersection(path.parts)
        and AMD_CALL.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
