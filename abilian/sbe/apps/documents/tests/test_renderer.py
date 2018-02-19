from __future__ import absolute_import, print_function, unicode_literals

from pytest import fixture

from abilian.sbe.app import create_app

from ..cmis.renderer import Feed, to_xml
from ..models import Document, Folder

pytest_plugins = ['abilian.conftest']


@fixture
def app(config):
    return create_app(config=config)


def test_folder_renderer(app_context):
    folder = Folder(name="tototiti")
    result = to_xml(folder)
    assert "tototiti" in result
    assert "cmis:folder" in result


def test_document_renderer(app_context):
    document = Document(name="tototiti")
    result = to_xml(document)
    assert "tototiti" in result
    assert "cmis:document" in result
    assert "<?xml" in result

    result = to_xml(document, no_xml_header=True)
    assert "<?xml" not in result


def test_feed_renderer(app_context):
    folder = Folder(title="Toto Titi")
    document = Document(title="tatatutu")
    feed = Feed(folder, [document])
    result = feed.to_xml()

    assert "Toto Titi" in result
    assert "tatatutu" in result
