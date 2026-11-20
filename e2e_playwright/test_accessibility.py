# Copyright (c) 2012-2024, Abilian SAS

"""axe-core on every kind of page, against WCAG 2 A and AA.

Dialogs are opened first, all at once, so that their fields are looked at too;
one on top of another is not something axe minds for names and labels.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from surfaces import all_paths

if TYPE_CHECKING:
    from playwright.sync_api import Page

AXE = pathlib.Path(__file__).parent.parent / "vite/node_modules/axe-core/axe.min.js"

RUN_AXE = """async () => {
  document.querySelectorAll("dialog").forEach((d) => d.setAttribute("open", ""));
  const results = await axe.run(document, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] },
  });
  return results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    nodes: v.nodes.slice(0, 3).map((n) => n.target.join(" ")),
    count: v.nodes.length,
  }));
}"""


@pytest.mark.parametrize("width", [375, 1280])
def test_no_page_has_wcag_violations(
    logged_in: Page, base_url: str, width: int
) -> None:
    page = logged_in
    source = AXE.read_text(encoding="utf-8")
    paths = all_paths(page, base_url)
    page.set_viewport_size({"width": width, "height": 800})

    found = []
    for path in paths:
        page.goto(f"{base_url}{path}", wait_until="networkidle")
        # evaluate, not add_script_tag: the policy refuses an inline script.
        page.evaluate(source)
        found += [
            f"{path}: {v['id']} ({v['impact']}, {v['count']}): {v['nodes']}"
            for v in page.evaluate(RUN_AXE)
        ]

    assert not found, "\n".join(found)


def test_skip_link_shows_on_focus(logged_in: Page, base_url: str) -> None:
    """On a page with the bar to skip; signing in has none. ADS moves the link above
    the screen until it has the focus."""
    page = logged_in
    page.goto(f"{base_url}/", wait_until="networkidle")
    link = page.get_by_role("link", name="Skip to content")

    hidden = link.bounding_box()
    link.focus()
    shown = link.bounding_box()

    assert hidden
    assert shown
    assert hidden["y"] + hidden["height"] <= 0
    assert shown["y"] >= 0
