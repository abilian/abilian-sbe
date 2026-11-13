# Copyright (c) 2012-2024, Abilian SAS

"""Nothing the Content Security Policy would block.

The policy has neither 'unsafe-inline' nor 'unsafe-eval', so an inline script or
handler, or an expression only `eval` could run, fails in the browser and nowhere
else: the page still returns 200 and the button does nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import abilian

ROOT = Path(abilian.__file__).parent
VENDORED = {"pdfjs", "font-awesome", "highlightjs", "vite"}

JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)
INLINE_SCRIPT = re.compile(
    r"""<script(?![^>]*\b(?:src=|type=["']application/json["']))[^>]*>""",
)
INLINE_HANDLER = re.compile(r"""<[a-zA-Z][^<>]*\son[a-z]+=["']""")
LEGACY_JS = re.compile(r"""\$\(|\bjQuery\b|\bdeferJS\b""")
#: What Alpine's CSP build cannot parse, or refuses: found only when the element
#: renders, otherwise.
ALPINE_REFUSED = re.compile(
    r"""\bx-html\b|(?:\bx-[a-z:.-]+|@[a-z:.-]+|\s:[a-z-]+)="[^"]*(?:=>|\bfunction\b|\bnew\s)""",
)


def sources() -> list[Path]:
    return [
        path
        for pattern in ("*.html", "*.py")
        for path in ROOT.rglob(pattern)
        if not VENDORED.intersection(path.parts)
    ]


def offenders(pattern: re.Pattern[str], paths: list[Path]) -> list[str]:
    found = []
    for path in paths:
        text = JINJA_COMMENT.sub("", path.read_text(encoding="utf-8"))
        found += [
            f"{path.relative_to(ROOT)}: {match.group(0)[:70]}"
            for match in pattern.finditer(text)
        ]
    return found


def test_no_inline_scripts() -> None:
    assert offenders(INLINE_SCRIPT, sources()) == []


def test_no_inline_event_handlers() -> None:
    assert offenders(INLINE_HANDLER, sources()) == []


def test_no_jquery_left_in_templates() -> None:
    templates = [path for path in sources() if path.suffix == ".html"]
    assert offenders(LEGACY_JS, templates) == []


def test_no_alpine_expression_the_csp_build_refuses() -> None:
    assert offenders(ALPINE_REFUSED, sources()) == []
