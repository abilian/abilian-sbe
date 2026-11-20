# Copyright (c) 2012-2024, Abilian SAS

"""No page scrolls sideways, on a phone or anywhere else.

A wide table may scroll inside its own container; the page itself may not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from surfaces import all_paths

if TYPE_CHECKING:
    from playwright.sync_api import Page

#: What sticks out past the right edge, leaving out what is inside a container
#: that scrolls or clips it, so that the failure names the culprit.
FIND_OVERFLOW = """() => {
  const width = document.documentElement.clientWidth;
  if (document.documentElement.scrollWidth <= width) return null;
  const clipped = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o !== "visible") return true;
    }
    return false;
  };
  const culprits = [...document.body.querySelectorAll("*")]
    .filter((el) => el.getBoundingClientRect().right > width + 1 && !clipped(el))
    .slice(0, 3)
    .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 50)}`);
  return `${document.documentElement.scrollWidth}px wide: ${culprits.join(", ")}`;
}"""


@pytest.mark.parametrize("width", [375, 768, 1440])
def test_no_page_scrolls_sideways(logged_in: Page, base_url: str, width: int) -> None:
    page = logged_in
    paths = all_paths(page, base_url)
    page.set_viewport_size({"width": width, "height": 800})

    overflowing = {}
    for path in paths:
        page.goto(f"{base_url}{path}", wait_until="networkidle")
        if found := page.evaluate(FIND_OVERFLOW):
            overflowing[path] = found

    assert not overflowing, "\n".join(f"{k}: {v}" for k, v in overflowing.items())
