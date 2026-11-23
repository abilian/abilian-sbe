# Copyright (c) 2012-2024, Abilian SAS

"""LibreOffice and pdftotext handlers, run against stub executables."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from abilian.services.conversion.exceptions import ConversionError
from abilian.services.conversion.handler_lock import init_conversion_lock_dir
from abilian.services.conversion.handlers import (
    LibreOfficePdfHandler,
    PdfToTextHandler,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from abilian.services.conversion import converter

    monkeypatch.setattr(converter, "tmp_dir", tmp_path, raising=False)
    init_conversion_lock_dir(str(tmp_path))
    return tmp_path


def make_script(directory: Path, name: str, body: str) -> str:
    """Write an executable shell script standing in for a real tool."""
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)
    return str(path)


def handler_with(soffice: str | None) -> LibreOfficePdfHandler:
    handler = LibreOfficePdfHandler()
    handler.soffice = soffice
    return handler


def test_missing_libreoffice_is_a_conversion_error(tmp_dir: Path) -> None:
    with pytest.raises(ConversionError, match="LibreOffice not available"):
        handler_with(None).convert(b"doc")


def test_libreoffice_failure_is_a_conversion_error(tmp_dir: Path) -> None:
    soffice = make_script(tmp_dir, "soffice-fail", "exit 3")
    with pytest.raises(ConversionError):
        handler_with(soffice).convert(b"doc")


def test_libreoffice_timeout_is_a_conversion_error(tmp_dir: Path) -> None:
    handler = handler_with(make_script(tmp_dir, "soffice-slow", "sleep 10"))
    handler.run_timeout = 0.2
    with pytest.raises(ConversionError, match="timeout"):
        handler.convert(b"doc")


def test_libreoffice_output_is_returned_then_deleted(tmp_dir: Path) -> None:
    # The last argument is the input file; soffice writes <stem>.pdf beside it.
    body = 'for last; do :; done; printf PDF > "${last%.*}.pdf"'
    soffice = make_script(tmp_dir, "soffice-ok", body)
    assert handler_with(soffice).convert(b"doc") == b"PDF"
    assert not list(tmp_dir.glob("*.pdf"))


def test_pdftotext_output_is_read_as_utf8(
    tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = 'printf "caf\\303\\251 \\377" > "$2"'
    poppler = tmp_dir / "poppler"
    poppler.mkdir()
    make_script(poppler, "pdftotext", body)
    monkeypatch.setenv("POPPLER_BIN", str(poppler))
    assert PdfToTextHandler().convert(b"pdf") == "café �"
