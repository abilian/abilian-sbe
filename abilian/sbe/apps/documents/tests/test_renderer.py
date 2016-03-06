from abilian.sbe.testing import BaseTestCase

from ..cmis.renderer import Feed, to_xml
from ..models import Document, Folder


class RendererTestCase(BaseTestCase):

    def test_folder_renderer(self):
        with self.app.test_client():
            folder = Folder(name="tototiti")
            result = to_xml(folder)
            assert "tototiti" in result
            assert "cmis:folder" in result

    def test_document_renderer(self):
        document = Document(name="tototiti")
        result = to_xml(document)
        assert "tototiti" in result
        assert "cmis:document" in result
        assert "<?xml" in result

        result = to_xml(document, no_xml_header=True)
        assert "<?xml" not in result

    def test_feed_renderer(self):
        folder = Folder(title="Toto Titi")
        document = Document(title="tatatutu")
        feed = Feed(folder, [document])
        result = feed.to_xml()

        assert "Toto Titi" in result
        assert "tatatutu" in result
