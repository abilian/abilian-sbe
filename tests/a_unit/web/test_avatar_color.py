# Copyright (c) 2012-2024, Abilian SAS

"""A user's default avatar keeps its colour across processes.

It was derived from `hash()`, which Python salts per process, so the colour
changed on every restart and could differ between two workers serving the same
page.
"""

from __future__ import annotations

import os
import subprocess
import sys

SNIPPET = (
    "from abilian.web.views.images import avatar_color;"
    "print(avatar_color('Jane Doe', 'jane@example.com'))"
)


def _color_in_a_fresh_process(hash_seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    result = subprocess.run(
        [sys.executable, "-c", SNIPPET],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_the_colour_does_not_depend_on_the_process() -> None:
    assert _color_in_a_fresh_process("1") == _color_in_a_fresh_process("2")
