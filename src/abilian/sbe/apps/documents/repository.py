# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.core.sqlalchemy.session import session_of
from abilian.services.security import READ, Permission, security

from .models import BaseContent, CmisObject, Document, Folder

if TYPE_CHECKING:
    from flask import Flask

    from abilian.core.models.subjects import User


class ContentRepository:
    """A simple document repository, implementing the basic functionalities of
    the CMIS model."""

    def __init__(self, app: Flask | None = None) -> None:
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        # self.app = app
        app.extensions["content_repository"] = self

    @property
    def root_folder(self) -> Folder:
        folder = Folder.query.filter(Folder.parent == None).first()
        if folder:
            return folder

        # Should only happen during tests
        folder = Folder(title="root")
        return folder

    def get_object(self, id: int | None = None, path: str | None = None):
        """Get the CMIS object (document or folder) with either the given `id`
        or the given `path`.

        Returns None if the object doesn't exist.
        """
        if id:
            return self.get_object_by_id(id)
        if path:
            return self.get_object_by_path(path)
        msg = "id or path must be not null."
        raise ValueError(msg)

    #
    # Id based navigation
    #
    def get_object_by_id(self, id: int) -> BaseContent | None:
        """Get the CMIS object (document or folder) with the given `id`.

        Returns None if the object doesn't exist.
        """
        obj = CmisObject.query.get(id)
        # if obj is not None and not isinstance(obj, CmisObject):
        #     return None
        return obj

    def get_folder_by_id(self, id: int) -> Folder | None:
        """Get the folder with the given `id`.

        Returns None if the folder doesn't exist.
        """
        return Folder.query.get(id)

    def get_document_by_id(self, id: int) -> Document | None:
        """Get the document with the given `id`.

        Returns None if the document doesn't exist.
        """
        return Document.query.get(id)

    #
    # Path based navigation
    #
    def get_object_by_path(self, path: str) -> Folder | Document | None:
        """Gets the CMIS object (document or folder) with the given `path`.

        Returns None if the object doesn't exist.
        """
        return self.root_folder.get_object_by_path(path)

    def get_folder_by_path(self, path: str) -> Folder | None:
        """Gets the folder with the given `path`.

        Returns None if the folder doesn't exist.
        """
        obj = self.root_folder.get_object_by_path(path)
        return obj if isinstance(obj, Folder) else None

    def get_document_by_path(self, path: str) -> Document | None:
        """Gets the document with the given `path`.

        Returns None if the document doesn't exist.
        """
        obj = self.root_folder.get_object_by_path(path)
        return obj if isinstance(obj, Document) else None

    #
    # COPY / MOVE support
    #
    def copy_object(
        self, obj: Folder | Document, dest_folder: Folder, dest_title: str | None = None
    ) -> Folder | Document:
        # Appended to the destination's collection, which cascades the copy into
        # its session: a backref (`parent=dest_folder`) no longer does.
        match obj:
            case Folder():
                new_folder = obj.clone(title=dest_title)
                dest_folder.subfolders.append(new_folder)
                for child in obj.children:
                    self.copy_object(child, new_folder)
                return new_folder
            case Document():
                new_document = obj.clone(title=dest_title)
                dest_folder.documents.append(new_document)
                return new_document
            case _:
                msg = f"Only folders and documents can be copied, not {obj!r}"
                raise TypeError(msg)

    def move_object(
        self, obj: CmisObject, dest_folder: Folder, dest_title: str | None = None
    ) -> None:
        obj.parent = dest_folder
        # Leaving its old folder expunges an object not yet flushed
        # (delete-orphan), and a backref no longer adds it back: add it.
        session_of(dest_folder).add(obj)
        if dest_title:
            obj.title = dest_title

    def rename_object(self, obj: CmisObject, title: str) -> None:
        obj.title = title

    def delete_object(self, obj: CmisObject) -> None:
        if obj.is_root_folder:
            msg = "Can't delete root folder."
            raise Exception(msg)

        session = session_of(obj)
        obj.__path_before_delete = obj.path  # for audit log.
        parent = obj.parent
        collection = parent.subfolders if obj.is_folder else parent.documents
        session.delete(obj)
        collection.remove(obj)

    #
    # Locking (TODO)
    #
    def is_locked(self, obj) -> bool:
        return False

    def can_unlock(self, obj) -> bool:
        return True

    def lock(self, obj) -> str:
        return "???"

    def unlock(self, obj) -> None:
        pass

    #
    # Security / access rights
    #
    def has_permission(
        self, user: User, permission: Permission, obj: CmisObject
    ) -> bool:
        assert isinstance(permission, Permission)
        return security.has_permission(user, permission, obj, inherit=True)

    def has_access(self, user: User, obj: CmisObject) -> bool:
        """Checks that user has actual right to reach this object, 'read'
        permission on each of object's parents."""
        current = obj
        while current.parent is not None:
            if not self.has_permission(user, READ, current):
                return False
            current = current.parent
        return True


content_repository = ContentRepository()
