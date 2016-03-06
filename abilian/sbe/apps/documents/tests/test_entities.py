# coding=utf-8

from unittest import TestCase, skip

from abilian.sbe.apps.documents.models import Document, Folder, icon_for


def check_editable(object):
    if hasattr(object, '__editable__'):
        for k in object.__editable__:
            assert hasattr(object, k)


def test_title_prevails():
    f = Folder(name=u'name', title=u'title')
    assert f.title == u'title'
    assert f.name == u'title'

    f = Folder(name=u'name', title=None)
    assert f.title == u'name'
    assert f.name == u'name'

    f = Folder(name=u'name')
    assert f.title == u'name'
    assert f.name == u'name'


def test_folder_editables():
    root = Folder(title="/")
    check_editable(root)


def test_folder_can_create_documents():
    root = Folder(title="/")

    document = root.create_document("doc")

    assert len(root.children) == 1
    assert document.title == "doc"
    assert document.path == "/doc"
    assert document in root.documents
    assert document in root.children
    assert document.parent == root


def test_folder_can_create_subfolders():
    root = Folder(title="/")

    subfolder = root.create_subfolder("folder")
    assert len(root.children) == 1
    assert subfolder.title == "folder"
    assert subfolder.path == "/folder"
    assert subfolder in root.subfolders
    assert subfolder in root.children
    assert subfolder.parent == root


def test_nested_subobjects():
    root = Folder(title="/")
    subfolder = root.create_subfolder("folder1")
    subsubfolder = subfolder.create_subfolder("folder2")
    document = subfolder.create_document("doc")

    assert len(root.children) == 1
    assert len(subfolder.children) == 2
    assert subsubfolder.title == "folder2"
    assert subsubfolder.path == "/folder1/folder2"
    assert document.title == "doc"
    assert document.path == "/folder1/doc"

    assert root.get_object_by_path("/folder1") == subfolder
    assert root.get_object_by_path("/folder1/folder2") == subsubfolder
    assert root.get_object_by_path("/folder1/doc") == document


def test_folder_is_clonable():
    root = Folder(title="/")
    clone = root.clone()

    assert clone.title == root.title
    assert clone.path == root.path


# FIXME: skipped for now as these tests break other tests down the line (in wiki).
@skip
class TestDocument(TestCase):

    def test_document_editables(self):
        doc = Document()
        check_editable(doc)

    def test_content_length(self):
        doc = Document()
        doc.set_content("tototiti", "application/binary")
        assert doc.content_length == len("tototiti")

    def test_document_is_clonable(self):
        root = Folder(title="/")
        doc = root.create_document(title="toto")
        doc.content = "tototiti"

        clone = doc.clone()
        assert clone.title == doc.title

    def test_document_has_an_icon(self):
        root = Folder(title="/")
        doc = root.create_document(title="toto")
        doc.content_type = "image/jpeg"
        filename = doc.icon.split("/")[-1]
        assert filename in ("jpg.png", "jpeg.png"), doc.icon

    def test_icon_from_mime_type(self):
        icon = icon_for("text/html")
        filename = icon.split("/")[-1]
        assert filename in ("html.png", "htm.png"), icon
