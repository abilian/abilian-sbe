# Copyright (c) 2026, Abilian SAS

"""What is kept of the HTML written in the rich text editor."""

from __future__ import annotations

from abilian.web.rich_text import sanitize_html


def test_a_script_goes_and_its_text_stays() -> None:
    html = '<p>Hi<script>alert("x")</script></p>'

    assert sanitize_html(html) == '<p>Hialert("x")</p>'


def test_only_the_alignment_of_a_paragraph_is_kept_of_its_style() -> None:
    html = '<p style="text-align: center; color: red">Hi</p>'

    assert sanitize_html(html) == '<p style="text-align: center;">Hi</p>'


def test_a_link_keeps_its_address_but_no_handler() -> None:
    html = '<a href="https://example.com" onclick="steal()">there</a>'

    assert sanitize_html(html) == '<a href="https://example.com">there</a>'
