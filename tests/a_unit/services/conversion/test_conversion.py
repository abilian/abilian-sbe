# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pytest import fixture, mark

from abilian.services.conversion.handler_lock import init_conversion_lock_dir
from abilian.services.conversion.handlers import HAS_LIBREOFFICE, HAS_PDFTOTEXT

if TYPE_CHECKING:
    from collections.abc import Iterator

    from abilian.services.conversion.service import Converter

#: What a PDF and a JPEG file start with.
PDF_MAGIC = b"%PDF-"
JPEG_MAGIC = b"\xff\xd8\xff"

# FIXME: tests that rely on OOo are disabled until we fix stability issues.


@fixture
def converter() -> Iterator[Converter]:
    from abilian.services.conversion import converter as converter_instance

    cache_dir = Path(tempfile.mkdtemp(suffix="unittest"))
    tmp_dir = Path(tempfile.mkdtemp(suffix="unittest"))
    converter_instance.init_work_dirs(cache_dir, tmp_dir)
    # No app here, so ConversionService.init_app() never runs; the handlers take
    # a file lock and need somewhere to put it.
    init_conversion_lock_dir(str(tmp_dir))
    yield converter_instance

    converter_instance.clear()


def read_file(file_name: str) -> bytes:
    return (Path(__file__).parent / "dummy_files" / file_name).read_bytes()


# To text
@mark.skipif(not HAS_PDFTOTEXT, reason="requires poppler or poppler-util")
def test_pdf_to_text(converter: Converter) -> None:
    blob = read_file("onepage.pdf")
    text = converter.to_text("", blob, "application/pdf")
    assert text


@mark.skipif(not HAS_PDFTOTEXT, reason="requires poppler or poppler-util")
def test_pdf_metadata_is_keyed_by_name(converter: Converter) -> None:
    """pdfinfo's keys were read as `str(bytes)`: "PDF:b'Pages'", so a document's
    page count was never found and every PDF had one page."""
    blob = read_file("rammstein.pdf")
    metadata = converter.get_metadata("", blob, "application/pdf")
    assert metadata["PDF:Pages"] == "16"


@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_word_to_text(converter: Converter) -> None:
    blob = read_file("test.doc")
    text = converter.to_text("", blob, "application/msword")
    assert text


@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_wordx_to_text(converter: Converter) -> None:
    blob = read_file("test.docx")
    text = converter.to_text("", blob, "application/msword")
    assert text


# def test_excel_to_text(converter):
#     blob = read_file("test.xls")
#     text = converter.to_text("", blob, "application/excel")


# To PDF
@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_odt_to_pdf(converter: Converter) -> None:
    blob = read_file("test.odt")
    pdf = converter.to_pdf("", blob, "application/vnd.oasis.opendocument.text")
    assert pdf.startswith(PDF_MAGIC)


@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_word_to_pdf(converter: Converter) -> None:
    blob = read_file("test.doc")
    pdf = converter.to_pdf("", blob, "application/msword")
    assert pdf.startswith(PDF_MAGIC)


@mark.skip("maybe bug due to ImageMagik settings")
def test_image_to_pdf(converter: Converter) -> None:
    blob = read_file("picture.jpg")
    pdf = converter.to_pdf("", blob, "image/jpeg")
    assert pdf.startswith(PDF_MAGIC)


# To images
@mark.skipif(not shutil.which("pdftoppm"), reason="requires pdftoppm (poppler)")
def test_pdf_to_images(converter: Converter) -> None:
    blob = read_file("onepage.pdf")
    image = converter.to_image("", blob, "application/pdf", 0)
    assert image.startswith(JPEG_MAGIC)


@mark.skipif(
    not HAS_PDFTOTEXT or not HAS_LIBREOFFICE, reason="requires poppler or poppler-util"
)
def test_word_to_images(converter: Converter) -> None:
    blob = read_file("test.doc")
    image = converter.to_image("", blob, "application/msword", 0)
    assert image.startswith(JPEG_MAGIC)


def test_empty_cached_text_is_a_cache_hit(converter: Converter) -> None:
    """An empty text is a valid result: it was converted again on every call."""
    converter.cache[("txt", "digest")] = ""
    # No handler takes this type: a miss would raise HandlerNotFoundError.
    assert converter.to_text("digest", b"", "application/x-unknown") == ""


def test_cache_write_leaves_no_temporary_file(converter: Converter) -> None:
    converter.cache[("pdf", "digest")] = b"first"
    converter.cache[("pdf", "digest")] = b"second"
    assert converter.cache.get_bytes(("pdf", "digest")) == b"second"
    assert [p.name for p in (converter.cache_dir / "pdf").iterdir()] == ["digest.blob"]
