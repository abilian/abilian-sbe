# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import contextlib
import glob
import os
import re
import shutil
import subprocess
import threading
import traceback
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from magic import Magic

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
    result = shutil.which("pdftotext") is not None
    if not result:
        logger.warning("has_pdftotext(): {result}", result=result)
        logger.warning("has_pdftotext() PATH: {path}", path=os.environ["PATH"])
    return result


def has_libreoffice() -> bool:
    result = shutil.which("soffice") is not None
    if not result:
        logger.warning("has_libreoffice(): {result}", result=result)
        logger.warning("has_libreoffice() PATH: {path}", path=os.environ["PATH"])
    return result


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

    @property
    def mime_sniffer(self):
        return Magic(mime=True)

    @property
    def encoding_sniffer(self) -> Magic:
        return Magic(mime_encoding=True)

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
    def convert(self, blob: bytes, **kw):
        pass


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

            converted = open(out_fn, "rb").read()
            try:
                encoding = self.encoding_sniffer.from_file(out_fn)
            except Exception:
                encoding = None

        if encoding in ("binary", None):
            encoding = "ascii"
        try:
            converted_unicode = str(converted, encoding, errors="ignore")
        except Exception:
            traceback.print_exc()
            converted_unicode = str(converted, errors="ignore")

        return converted_unicode


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
    soffice = "soffice"
    _process: subprocess.Popen

    def init_app(self, app: Flask) -> None:
        soffice = app.config.get("SOFFICE_LOCATION")

        if soffice:
            # make absolute path: avoid errors when running with different CWD
            soffice_path = Path(soffice).resolve()
            found = soffice_path.is_file()
            if not found:
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
            self.log.error("Can't find LibreOffice executable")
            soffice = None

        self.soffice = soffice

    @acquire_lock("LibreOfficePdfHandler")
    def convert(self, blob: bytes, **kw: Any) -> bytes:
        """Convert using soffice converter."""
        timeout = self.run_timeout
        with make_temp_file(blob, tmp_dir=self.tmp_dir) as in_fn:
            cmd = [
                self.soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(self.tmp_dir),
                str(in_fn),
            ]

            def run_soffice() -> None:
                try:
                    self._process = subprocess.Popen(
                        cmd, close_fds=True, cwd=str(self.tmp_dir)
                    )
                    self._process.communicate()
                except subprocess.CalledProcessError as e:
                    logger.debug("CalledProcessError for soffice")
                    logger.debug("returncode:{returncode}", returncode=e.returncode)
                    logger.debug("e.cmd:{cmd}", cmd=e.cmd)
                    logger.debug("stdout:{stdout}", stdout=e.stdout)
                    logger.debug("stderr:{stderr}", stderr=e.stderr)
                    raise ConversionError from e
                except Exception as e:
                    logger.opt(exception=True).error(
                        "soffice error: {error}", error=str(e)
                    )
                    raise ConversionError from e

            run_thread = threading.Thread(target=run_soffice)
            run_thread.start()
            run_thread.join(timeout)
            try:
                if run_thread.is_alive():
                    # timeout reached
                    self._process.terminate()
                    if self._process.poll() is not None:
                        try:
                            self._process.kill()
                        except OSError:
                            logger.warning(
                                "Failed to kill process {process}",
                                process=self._process,
                            )

                    msg = f"Conversion timeout ({timeout})"
                    raise ConversionError(msg)

                out_fn = f"{os.path.splitext(in_fn)[0]}.pdf"
                converted = open(out_fn, "rb").read()
                return converted
            finally:
                if hasattr(self, "_process"):
                    del self._process
