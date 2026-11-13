# Copyright (c) 2012-2024, Abilian SAS

"""Guard against Tailwind v3 utilities that v4 silently dropped.

These fail quietly: the class stays in the markup, Tailwind emits nothing for
it, and the element renders with the un-modified value. `ring-opacity-5` was
the expensive one -- every navbar dropdown drew a solid black ring instead of
a 5% one, and nothing in the build or the test suite noticed.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).parent.parent.parent / "src"

#: Utilities removed in Tailwind v4, with what replaced them.
REMOVED = {
    r"\b(?:bg|text|border|ring|divide|placeholder)-opacity-\d+\b": (
        "opacity utilities are gone; use the slash syntax, e.g. `ring-black/5`"
    ),
    r"\boverflow-ellipsis\b": "renamed to `text-ellipsis`",
    r"\bdecoration-(?:slice|clone)\b": "renamed to `box-decoration-{slice,clone}`",
}


def _sources() -> list[Path]:
    files = list(SRC.rglob("*.html"))
    # Some class strings are built in Python (action.py, nav.py).
    files += [p for p in SRC.rglob("*.py") if "static" not in p.parts]
    return files


def test_no_removed_tailwind_utilities() -> None:
    offences: list[str] = []

    for path in _sources():
        text = path.read_text(errors="ignore")
        for pattern, hint in REMOVED.items():
            for match in re.finditer(pattern, text):
                line = text[: match.start()].count("\n") + 1
                rel = path.relative_to(SRC.parent)
                offences.append(f"{rel}:{line}: {match.group(0)} -- {hint}")

    assert not offences, "Tailwind v3 utilities that v4 does not emit:\n" + "\n".join(
        offences
    )
