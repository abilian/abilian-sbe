import pytest
from pytest import fixture
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from abilian.sbe.app import Application
from abilian.sbe.apps.documents.models import Document, Folder
from abilian.sbe.apps.documents.repository import Repository


@fixture
def repository(app: Application) -> Repository:
    repository = Repository()
    repository.init_app(app)
    return repository


@fixture
def root(session: Session) -> Folder:
    root = Folder(title="")
    session.add(root)
    session.flush()
    return root


def test_create_doc(root: Folder, session: Session) -> None:
    doc = root.create_document("doc")
    session.flush()
    assert doc.path == "/doc"
    assert len(root.children) == 1
    assert not doc.is_root_folder


def test_create_folder(root: Folder, session: Session) -> None:
    folder = root.create_subfolder("folder")
    session.flush()
    assert folder.title == "folder"
    assert folder.name == "folder"
    assert folder.path == "/folder"
    assert len(root.children) == 1
    assert len(folder.children) == 0
    assert not folder.is_root_folder


def test_move(root: Folder, repository: Repository) -> None:
    doc = root.create_document("doc")
    folder = root.create_subfolder("folder")

    repository.move_object(doc, folder, "newdoc")
    assert doc in folder.children
    assert doc not in root.children
    assert len(root.children) == 1
    assert len(folder.children) == 1
    assert doc.title == "newdoc"
    assert doc.path == "/folder/newdoc"


def test_copy(root: Folder, repository: Repository) -> None:
    doc = root.create_document("doc")
    folder = root.create_subfolder("folder")

    doc_copy = repository.copy_object(doc, folder, "copydoc")

    assert len(root.children) == 2
    assert len(folder.children) == 1
    assert doc_copy.title == "copydoc"
    assert doc_copy.name == "copydoc"
    assert doc_copy.path == "/folder/copydoc"
    assert doc_copy in folder.children


def test_copy_nested_folders(root: Folder, repository: Repository) -> None:
    folder1 = root.create_subfolder("folder1")
    folder2 = root.create_subfolder("folder2")
    subfolder = folder1.create_subfolder("subfolder")

    folder1_copy = repository.copy_object(folder1, folder2)

    assert len(root.children) == 2
    assert folder1 in root.children
    assert folder2 in root.children

    assert len(folder1.children) == 1
    assert subfolder in folder1.children

    assert len(folder2.children) == 1
    assert folder1_copy in folder2.children


def test_move_nested_folders(root: Folder, repository: Repository) -> None:
    folder1 = root.create_subfolder("folder1")
    folder2 = root.create_subfolder("folder2")
    subfolder = folder1.create_subfolder("subfolder")  # noqa

    repository.move_object(folder1, folder2)

    assert len(root.children) == 1
    assert len(folder1.children) == 1


def test_rename(root: Folder, repository: Repository) -> None:
    folder = root.create_subfolder("folder")
    doc = folder.create_document("doc")

    repository.rename_object(doc, "doc1")
    assert doc.title == "doc1"
    assert doc.name == "doc1"
    assert doc.path == "/folder/doc1"

    repository.rename_object(folder, "folder1")
    assert folder.title == "folder1"
    assert folder.name == "folder1"
    assert folder.path == "/folder1"
    assert doc.path == "/folder1/doc1"


def test_delete(root: Folder, repository: Repository, session: Session) -> None:
    doc = root.create_document("doc")
    folder = root.create_subfolder("folder")
    session.flush()

    assert doc.parent == root
    assert folder.parent == root
    assert doc in root.children
    assert folder in root.children
    assert not doc.is_root_folder
    assert not folder.is_root_folder

    doc_id = doc.id
    folder_id = folder.id

    repository.delete_object(doc)
    repository.delete_object(folder)
    assert len(root.children) == 0

    session.flush()
    assert Folder.query.get(folder_id) is None
    assert Document.query.get(doc_id) is None

    # test delete tree
    folder = root.create_subfolder("folder")
    sub = folder.create_subfolder("subfolder")  # noqa
    doc = folder.create_document("doc")  # noqa
    session.flush()

    repository.delete_object(folder)
    assert len(root.children) == 0
    assert Folder.query.all() == [root]
    assert Document.query.all() == []


def test_no_duplicate_name(root: Folder, session: Session) -> None:
    root.create_subfolder("folder_1")
    root.create_subfolder("folder_1")
    with pytest.raises(IntegrityError):
        session.flush()
