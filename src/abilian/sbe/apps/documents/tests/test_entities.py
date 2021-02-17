from typing import Union

from flask.ctx import AppContext
from pytest import fixture
from sqlalchemy.orm import Session

from abilian.sbe.app import Application, create_app
from abilian.sbe.apps.documents.models import Document, Folder, icon_for


@fixture
def app(config: type) -> Application:
    return create_app(config=config)


def check_editable(object: Union[Document, Folder]) -> None:
    if hasattr(object, "__editable__"):
        for k in object.__editable__:
            assert hasattr(object, k)


def test_title_prevails() -> None:
    f = Folder(name="name", title="title")
    assert f.title == "title"
    assert f.name == "title"

    f = Folder(name="name", title=None)
    assert f.title == "name"
    assert f.name == "name"

    f = Folder(name="name")
    assert f.title == "name"
    assert f.name == "name"


def test_folder_editables() -> None:
    root = Folder(title="/")
    check_editable(root)


def test_folder_can_create_documents() -> None:
    root = Folder(title="/")

    document = root.create_document("doc")

    assert len(root.children) == 1
    assert document.title == "doc"
    assert document.path == "/doc"
    assert document in root.documents
    assert document in root.children
    assert document.parent == root


def test_folder_can_create_subfolders() -> None:
    root = Folder(title="/")

    subfolder = root.create_subfolder("folder")
    assert len(root.children) == 1
    assert subfolder.title == "folder"
    assert subfolder.path == "/folder"
    assert subfolder in root.subfolders
    assert subfolder in root.children
    assert subfolder.parent == root


def test_nested_subobjects() -> None:
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


def test_folder_is_clonable() -> None:
    root = Folder(title="/")
    clone = root.clone()

    assert clone.title == root.title
    assert clone.path == root.path


def test_document_editables() -> None:
    doc = Document()
    check_editable(doc)


def test_content_length(session: Session) -> None:
    doc = Document(title="toto")
    doc.set_content(b"tototiti", "application/binary")
    assert doc.content_length == len("tototiti")


def test_document_is_clonable(session: Session) -> None:
    root = Folder(title="/")
    doc = root.create_document(title="toto")
    doc.content = b"tototiti"

    clone = doc.clone()
    assert clone.title == doc.title
    assert clone.content == doc.content


def test_document_has_an_icon(app_context: AppContext) -> None:
    root = Folder(title="/")
    doc = root.create_document(title="toto")
    doc.content_type = "image/jpeg"
    filename = doc.icon.split("/")[-1]
    assert filename in ("jpg.png", "jpeg.png"), doc.icon


def test_icon_from_mime_type(app_context: AppContext) -> None:
    icon = icon_for("text/html")
    filename = icon.split("/")[-1]
    assert filename in ("html.png", "htm.png"), icon
