# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals

from pytest import mark

from ..cmis.renderer import Feed, to_xml
from ..models import Document, Folder


@mark.usefixtures("app_context")
def test_folder_renderer():
    folder = Folder(name="tototiti")
    result = to_xml(folder)
    assert "tototiti" in result
    assert "cmis:folder" in result


@mark.usefixtures("app_context")
def test_document_renderer():
    document = Document(name="tototiti")
    result = to_xml(document)
    assert "tototiti" in result
    assert "cmis:document" in result
    assert "<?xml" in result

    result = to_xml(document, no_xml_header=True)
    assert "<?xml" not in result


@mark.usefixtures("app_context")
def test_feed_renderer():
    folder = Folder(title="Toto Titi")
    document = Document(title="tatatutu")
    feed = Feed(folder, [document])
    result = feed.to_xml()

    assert "Toto Titi" in result
    assert "tatatutu" in result
