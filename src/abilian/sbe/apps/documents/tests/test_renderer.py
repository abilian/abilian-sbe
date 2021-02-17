from pytest import mark

from abilian.sbe.apps.documents.cmis.renderer import Feed, to_xml
from abilian.sbe.apps.documents.models import Document, Folder


@mark.usefixtures("app_context")
def test_folder_renderer() -> None:
    folder = Folder(name="tototiti")
    result = to_xml(folder)
    assert "tototiti" in result
    assert "cmis:folder" in result


@mark.usefixtures("app_context")
def test_document_renderer() -> None:
    document = Document(name="tototiti")
    result = to_xml(document)
    assert "tototiti" in result
    assert "cmis:document" in result
    assert "<?xml" in result

    result = to_xml(document, no_xml_header=True)
    assert "<?xml" not in result


@mark.usefixtures("app_context")
def test_feed_renderer() -> None:
    folder = Folder(title="Toto Titi")
    document = Document(title="tatatutu")
    feed = Feed(folder, [document])
    result = feed.to_xml()

    assert "Toto Titi" in result
    assert "tatatutu" in result
