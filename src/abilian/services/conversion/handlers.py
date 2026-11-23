# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import contextlib
import glob
import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from abilian.services.image import resize

from .exceptions import ConversionError
from .handler_lock import acquire_lock
from .util import get_tmp_dir, make_temp_file

if TYPE_CHECKING:
    from flask import Flask


def poppler_bin_util(util: str) -> str:
    if "POPPLER_BIN" not in os.environ:
        return ""
    path = Path(os.environ["POPPLER_BIN"]) / util
    if path.is_file():
        return str(path)
    return ""


# Quick check for tests
def has_pdftotext() -> bool:
    if poppler_bin_util("pdftotext"):
        return True
    return shutil.which("pdftotext") is not None


def has_libreoffice() -> bool:
    return shutil.which("soffice") is not None


HAS_PDFTOTEXT = has_pdftotext()
HAS_LIBREOFFICE = has_libreoffice()


class Handler(ABC):
    """Abstract base class for handlers."""

    accepts_mime_types: list[str] = []
    produces_mime_types: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        self.log = logger

    def init_app(self, app: Flask) -> None:
        pass

    @property
    def tmp_dir(self) -> Path:
        return get_tmp_dir()

    def accept(self, source_mime_type: str, target_mime_type: str) -> bool:
        """Generic matcher based on patterns."""

        match_source = False
        match_target = False

        for pat in self.accepts_mime_types:
            if re.match(f"^{pat}$", source_mime_type):
                match_source = True
                break

        for pat in self.produces_mime_types:
            if re.match(f"^{pat}$", target_mime_type):
                match_target = True
                break

        return match_source and match_target

    @abstractmethod
    def convert(self, blob: bytes, **kw: Any) -> Any:
        """Convert `blob` to the type the handler produces.

        Text handlers return a `str`, PDF handlers `bytes`, and image
        handlers a list of `bytes`, one image per page. The converter picks
        the handler by what it produces, which no single type can say.
        """


class PdfToTextHandler(Handler):
    accepts_mime_types = ["application/pdf", "application/x-pdf"]
    produces_mime_types = ["text/plain"]

    @acquire_lock("PdfToTextHandler")
    def convert(self, blob: bytes, **kw: Any) -> str:
        with make_temp_file(blob) as in_fn, make_temp_file() as out_fn:
            pdftotext = poppler_bin_util("pdftotext") or "pdftotext"
            try:
                subprocess.check_call([pdftotext, in_fn, out_fn])
            except Exception as e:
                msg = "pdftotext failed"
                raise ConversionError(msg) from e

            # pdftotext writes UTF-8 by default.
            return Path(out_fn).read_bytes().decode("utf-8", errors="replace")


class ImageMagickHandler(Handler):
    accepts_mime_types = ["image/.*"]
    produces_mime_types = ["application/pdf"]

    @acquire_lock("ImageMagickHandler")
    def convert(self, blob: bytes, **kw) -> bytes:
        with make_temp_file(blob) as in_fn, make_temp_file() as out_fn:
            try:
                subprocess.check_call(["convert", in_fn, f"pdf:{out_fn}"])
                converted = open(out_fn, "rb").read()
                return converted
            except Exception as e:
                msg = "convert failed"
                raise ConversionError(msg) from e


class PdfToPpmHandler(Handler):
    accepts_mime_types = ["application/pdf", "application/x-pdf"]
    produces_mime_types = ["image/jpeg"]

    @acquire_lock("PdfToPpmHandler")
    def convert(self, blob: bytes, size: int = 500, **kw) -> list[bytes]:
        """Size is the maximum horizontal size."""
        file_list: list[str] = []
        with make_temp_file(blob) as in_fn, make_temp_file() as out_fn:
            pdftoppm = poppler_bin_util("pdftoppm") or "pdftoppm"
            try:
                subprocess.check_call([pdftoppm, "-jpeg", in_fn, out_fn])
                file_list = sorted(glob.glob(f"{out_fn}-*.jpg"))

                converted_images = []
                for fn in file_list:
                    converted = resize(open(fn, "rb").read(), size, size)
                    converted_images.append(converted)
            except Exception as e:
                msg = "pdftoppm failed"
                raise ConversionError(msg) from e
            else:
                return converted_images
            finally:
                for fn in file_list:
                    with contextlib.suppress(OSError):
                        os.remove(fn)


class LibreOfficePdfHandler(Handler):
    """Handles conversion from office documents (MS-Office, OOo) to PDF.

    Uses LibreOffice in headless mode.
    """

    # TODO: add more if needed.
    accepts_mime_types = [
        "application/vnd.oasis.*",
        "application/msword",
        "application/mspowerpoint",
        "application/vnd.ms-powerpoint",
        "application/vnd.ms-excel",
        "application/vnd.ms-office",
        "application/ms-excel",
        "application/vnd.openxmlformats-officedocument.*",
        "text/rtf",
    ]
    produces_mime_types = ["application/pdf"]
    run_timeout = 60
    soffice: str | None = "soffice"

    def init_app(self, app: Flask) -> None:
        soffice = app.config.get("SOFFICE_LOCATION")

        if soffice:
            # make absolute path: avoid errors when running with different CWD
            soffice = str(Path(soffice).resolve())
            if not Path(soffice).is_file():
                self.log.error("Can't find executable {soffice}", soffice=soffice)

        elif Path("/usr/local/bin/soffice").is_file():
            soffice = "/usr/local/bin/soffice"

        elif Path("/usr/bin/soffice").is_file():
            soffice = "/usr/bin/soffice"

        elif Path("/opt/homebrew/bin/soffice").is_file():
            soffice = "/opt/homebrew/bin/soffice"

        if soffice:
            if not os.access(soffice, os.X_OK):
                self.log.warning('Not allowed to execute "{soffice}"', soffice=soffice)

        else:
            # Optional: the app runs without it, office documents just get
            # no preview or full text.
            self.log.warning("Can't find LibreOffice: office documents won't convert")
            soffice = None

        self.soffice = soffice

    @acquire_lock("LibreOfficePdfHandler")
    def convert(self, blob: bytes, **kw: Any) -> bytes:
        """Convert using soffice converter."""
        if not self.soffice:
            msg = "LibreOffice not available"
            raise ConversionError(msg)

        with make_temp_file(blob, tmp_dir=self.tmp_dir) as in_fn:
            out_path = Path(in_fn).with_suffix(".pdf")
            cmd = [
                self.soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(self.tmp_dir),
                in_fn,
            ]
            try:
                # run() kills soffice when the timeout expires.
                subprocess.run(
                    cmd,
                    cwd=self.tmp_dir,
                    timeout=self.run_timeout,
                    check=True,
                    capture_output=True,
                )
                # soffice may exit 0 without writing anything: reading the
                # missing file then fails like any other conversion failure.
                return out_path.read_bytes()
            except subprocess.TimeoutExpired as e:
                msg = f"Conversion timeout ({self.run_timeout}s)"
                raise ConversionError(msg) from e
            except subprocess.CalledProcessError as e:
                msg = f"soffice failed ({e.returncode}): {e.stderr!r}"
                raise ConversionError(msg) from e
            except OSError as e:
                msg = f"soffice failed: {e}"
                raise ConversionError(msg) from e
            finally:
                out_path.unlink(missing_ok=True)
