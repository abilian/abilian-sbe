from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import render_template


@dataclass(frozen=True)
class Page:
    context: dict[str, Any]

    def render(self):
        return render_template("wall/index.html", **self.context)
