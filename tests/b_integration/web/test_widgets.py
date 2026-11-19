# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

# Import for side effects (monkey-patch)
import abilian.web.forms
from abilian.web.forms.widgets import linkify_url, text2html

# Dpnt' remove
assert abilian.web.forms


EXPECTED = (
    '<a href="http://example.com">example.com</a>'
    '&nbsp;<i class="fa fa-external-link"></i>'
)


def test_http() -> None:
    value = "http://example.com"
    result = linkify_url(value)
    assert result == EXPECTED


def test_no_http() -> None:
    value = "example.com"
    result = linkify_url(value)
    assert result == EXPECTED


def test1() -> None:
    result = text2html("a")
    assert result == "a"


def test2() -> None:
    result = text2html("a\nb")
    assert str(result) == "<p>a</p>\n<p>b</p>"


def test3() -> None:
    result = text2html("a\n\nb")
    assert str(result) == "<p>a</p>\n<p>b</p>"


def test4() -> None:
    result = text2html("a\n<a>toto</a>")
    assert str(result) == "<p>a</p>\n<p>&lt;a&gt;toto&lt;/a&gt;</p>"
