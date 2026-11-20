"""Check that the built packages hold what a deployment needs, and no more.

Run by `make dist` on its output directory.
"""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

#: Each of these must match at least one file of the wheel.
REQUIRED = (
    "abilian/sbe/static/vite/main.js",
    "abilian/sbe/translations/fr/LC_MESSAGES/messages.mo",
    "abilian/translations/fr/LC_MESSAGES/messages.mo",
    "abilian/migrations/env.py",
    "abilian/migrations/alembic.ini",
)

#: No file of either package may have one of these in its path.
FORBIDDEN = ("local-notes/", "tests/", "docs/", "mockups/", "notes/", "__pycache__/")


def main(dist: Path) -> None:
    """Exit with an error message unless both packages pass."""
    (wheel,) = dist.glob("*.whl")
    (sdist,) = dist.glob("*.tar.gz")
    in_wheel = zipfile.ZipFile(wheel).namelist()
    in_sdist = tarfile.open(sdist).getnames()
    errors = [
        f"{wheel.name}: {path} is missing" for path in REQUIRED if path not in in_wheel
    ]
    errors += [
        f"{package.name}: {name} should not ship"
        for package, names in ((wheel, in_wheel), (sdist, in_sdist))
        for name in names
        if any(part in name for part in FORBIDDEN)
    ]
    if errors:
        sys.exit("\n".join(errors))
    print(f"{wheel.name} and {sdist.name}: OK")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
