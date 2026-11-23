# Copyright (c) 2026, Abilian SAS

"""The antivirus scans a file given by its path, as by its content."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


# The module: the package names its service instance `service` too.
antivirus = importlib.import_module("abilian.services.antivirus.service")


class StubClamd:
    """ClamAV's client, answering that every stream is clean."""

    def __init__(self) -> None:
        self.scanned: list[bytes] = []

    def instream(self, stream: BinaryIO) -> dict[str, tuple[str, None]]:
        self.scanned.append(stream.read())
        stream.close()
        return {"stream": ("OK", None)}


def test_a_file_given_by_its_path_is_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path as `str` was encoded with a function for an encoding: TypeError."""
    clamd = StubClamd()
    monkeypatch.setattr(antivirus, "clamd", clamd)
    path = tmp_path / "report.txt"
    path.write_bytes(b"Nothing to see.")

    assert antivirus.AntiVirusService().scan(str(path)) is True
    assert clamd.scanned == [b"Nothing to see."]
