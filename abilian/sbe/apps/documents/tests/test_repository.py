# coding=utf-8

from sqlalchemy.exc import IntegrityError

from abilian.core.extensions import db
from abilian.sbe.testing import BaseTestCase

from ..models import Document, Folder


class TestService(BaseTestCase):

    def setUp(self):
        super(TestService, self).setUp()
        self.repository = self.app.extensions['content_repository']
        self.root = Folder(title=u"")
        self.session.add(self.root)
        self.session.flush()

    def test_create_doc(self):
        root = self.root
        doc = root.create_document(u"doc")
        db.session.flush()
        assert doc.path == "/doc"
        assert len(root.children) == 1
        assert not doc.is_root_folder

    def test_create_folder(self):
        root = self.root
        folder = root.create_subfolder(u"folder")
        db.session.flush()
        self.assertEquals(folder.title, u'folder')
        self.assertEquals(folder.name, u'folder')
        assert folder.path == "/folder"
        assert len(root.children) == 1
        assert len(folder.children) == 0
        assert not folder.is_root_folder

    def test_move(self):
        root = self.root
        doc = root.create_document(u"doc")
        folder = root.create_subfolder(u"folder")

        self.repository.move_object(doc, folder, u"newdoc")
        assert doc in folder.children
        assert doc not in root.children
        assert len(root.children) == 1
        assert len(folder.children) == 1
        assert doc.title == "newdoc"
        assert doc.path == "/folder/newdoc"

    def test_copy(self):
        root = self.root
        doc = root.create_document(u"doc")
        folder = root.create_subfolder(u"folder")

        doc_copy = self.repository.copy_object(doc, folder, u"copydoc")

        assert len(root.children) == 2
        assert len(folder.children) == 1
        self.assertEquals(doc_copy.title, "copydoc")
        self.assertEquals(doc_copy.name, "copydoc")
        assert doc_copy.path == "/folder/copydoc"
        assert doc_copy in folder.children

    def test_copy_nested_folders(self):
        root = self.root
        folder1 = root.create_subfolder(u"folder1")
        folder2 = root.create_subfolder(u"folder2")
        subfolder = folder1.create_subfolder(u"subfolder")

        folder1_copy = self.repository.copy_object(folder1, folder2)

        assert len(root.children) == 2
        assert folder1 in root.children
        assert folder2 in root.children

        assert len(folder1.children) == 1
        assert subfolder in folder1.children

        assert len(folder2.children) == 1
        assert folder1_copy in folder2.children

    def test_move_nested_folders(self):
        root = self.root
        folder1 = root.create_subfolder(u"folder1")
        folder2 = root.create_subfolder(u"folder2")
        subfolder = folder1.create_subfolder(u"subfolder")  # noqa

        self.repository.move_object(folder1, folder2)

        assert len(root.children) == 1
        assert len(folder1.children) == 1

    def test_rename(self):
        root = self.root
        folder = root.create_subfolder(u"folder")
        doc = folder.create_document(u"doc")

        self.repository.rename_object(doc, u"doc1")
        self.assertEquals(doc.title, 'doc1')
        self.assertEquals(doc.name, 'doc1')
        assert doc.path == '/folder/doc1'

        self.repository.rename_object(folder, u"folder1")
        self.assertEquals(folder.title, 'folder1')
        self.assertEquals(folder.name, 'folder1')
        assert folder.path == '/folder1'
        assert doc.path == '/folder1/doc1'

    def test_delete(self):
        root = self.root

        doc = root.create_document(u"doc")
        folder = root.create_subfolder(u"folder")
        self.session.flush()

        assert doc.parent == root
        assert folder.parent == root
        assert doc in root.children
        assert folder in root.children
        assert not doc.is_root_folder
        assert not folder.is_root_folder

        doc_id = doc.id
        folder_id = folder.id

        self.repository.delete_object(doc)
        self.repository.delete_object(folder)
        assert len(root.children) == 0
        self.session.flush()

        assert Folder.query.get(folder_id) is None
        assert Document.query.get(doc_id) is None

        # test delete tree
        folder = root.create_subfolder(u"folder")
        sub = folder.create_subfolder(u'subfolder')  # noqa
        doc = folder.create_document(u"doc")  # noqa
        self.session.flush()

        self.repository.delete_object(folder)
        assert len(root.children) == 0
        assert Folder.query.all() == [root]
        assert Document.query.all() == []

    def test_no_duplicate_name(self):
        root = self.root
        root.create_subfolder(u'folder_1')
        root.create_subfolder(u'folder_1')
        try:
            self.session.flush()
            self.fail('Could create folders with duplicate name')
        except IntegrityError:
            pass
