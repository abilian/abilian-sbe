# Copyright (c) 2012-2024, Abilian SAS

"""Build what git does not keep: the compiled translations and the pages' scripts.

A package built from a checkout of the repository (`uv` from a git URL, say) would
otherwise lack both, and serve an untranslated site whose pages have no scripts.
The scripts are built only when they are missing: from an sdist, which carries
them but not their sources, there is nothing to build. Node comes from the
`nodejs-wheel-binaries` package, a build requirement, so the machine that builds
needs none.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

TRANSLATIONS = ("src/abilian/translations", "src/abilian/sbe/translations")
SCRIPTS = Path("src/abilian/sbe/static/vite")


class CustomBuildHook(BuildHookInterface):
    """Compile the translations, and build the scripts when they are missing."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Run before each build of the sdist or the wheel."""
        # An editable install is a development checkout: `make front
        # translations` builds both there, and Vite's server serves the scripts.
        if version == "editable":
            return
        root = Path(self.root)
        compile_translations(root)
        if not (root / SCRIPTS / "main.js").exists():
            build_scripts(root)


def compile_translations(root: Path) -> None:
    """Compile each catalog's .po file into the .mo file the app reads."""
    from babel.messages.frontend import CommandLineInterface

    for directory in TRANSLATIONS:
        status = CommandLineInterface().run(
            ["pybabel", "-q", "compile", "-d", str(root / directory)]
        )
        if status:
            msg = f"Could not compile the translations in {directory}"
            raise RuntimeError(msg)


def build_scripts(root: Path) -> None:
    """Build the pages' scripts with Vite, into the package's static folder."""
    from nodejs_wheel.executable import ROOT_DIR

    node_root = Path(ROOT_DIR)
    with tempfile.TemporaryDirectory() as shims:
        # The wheel's own `bin/npm` cannot find npm's code, and npm's scripts
        # call `npm` and `node` by name, through the shell: a one-line `npm` and
        # the wheel's `node` come first on the PATH.
        npm = Path(shims, "npm")
        npm.write_text(
            f'#!/bin/sh\nexec "{node_root}/bin/node" '
            f'"{node_root}/lib/node_modules/npm/bin/npm-cli.js" "$@"\n'
        )
        npm.chmod(0o755)
        path = os.pathsep.join([shims, str(node_root / "bin"), os.environ["PATH"]])
        env = {**os.environ, "PATH": path}
        for command in (["npm", "ci"], ["npm", "run", "build"]):
            subprocess.run(command, cwd=root / "vite", env=env, check=True)
