# coding=utf-8
"""
"""
from __future__ import absolute_import

import sqlalchemy as sa

from abilian.services.security import READ, security

from .models import CmisObject, Document, Folder


class SecurityException(Exception):
    pass


class Repository(object):
    """
    A simple document repository, implementing the basic functionalities of the
    CMIS model.
    """

    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.extensions['content_repository'] = self

    @property
    def root_folder(self):
        folder = Folder.query.filter(Folder.parent == None).first()
        if folder:
            return folder

        # Should only happen during tests
        folder = Folder(title=u'root')
        return folder

    def get_object(self, id=None, path=None):
        """
        Gets the CMIS object (document or folder) with either the given `id` or the
        given `path`. Returns None if the object doesn't exist.
        """
        if id:
            return self.get_object_by_id(id)
        else:
            return self.get_object_by_path(path)

    #
    # Id based navigation
    #
    def get_object_by_id(self, id):
        """Gets the CMIS object (document or folder) with the given `id`.

        Returns None if the object doesn't exist.
        """
        obj = CmisObject.query.get(id)
        if obj is not None and not isinstance(obj, CmisObject):
            return None
        return obj

    def get_folder_by_id(self, id):
        """Gets the folder with the given `id`.

        Returns None if the folder doesn't exist.
        """
        return Folder.query.get(id)

    def get_document_by_id(self, id):
        """Gets the document with the given `id`.

        Returns None if the document doesn't exist.
        """
        document = Document.query.get(id)
        return document

    #
    # Path based navigation
    #
    def get_object_by_path(self, path):
        """Gets the CMIS object (document or folder) with the given `path`.

        Returns None if the object doesn't exist.
        """
        return self.root_folder.get_object_by_path(path)

    def get_folder_by_path(self, path):
        """Gets the folder with the given `path`.

        Returns None if the folder doesn't exist.
        """
        obj = self.root_folder.get_object_by_path(path)
        if obj is None or not obj.is_folder:
            return None
        else:
            return obj

    def get_document_by_path(self, path):
        """Gets the document with the given `path`.

        Returns None if the document doesn't exist.
        """
        obj = self.root_folder.get_object_by_path(path)
        if obj is None or not obj.is_document:
            return None
        else:
            return obj

    #
    # COPY / MOVE support
    #
    def copy_object(self, obj, dest_folder, dest_title=None):
        new_obj = obj.clone(title=dest_title, parent=dest_folder)
        if obj.is_folder:
            for child in obj.children:
                self.copy_object(child, new_obj)
        return new_obj

    def move_object(self, obj, dest_folder, dest_title=None):
        obj.parent = dest_folder
        if dest_title:
            obj.title = dest_title

    def rename_object(self, obj, title):
        obj.title = title

    def delete_object(self, obj):
        if obj.is_root_folder:
            raise Exception("Can't delete root folder.")

        session = sa.orm.object_session(obj)
        setattr(obj, '__path_before_delete', obj.path)  # for audit log.
        parent = obj.parent
        collection = parent.subfolders if obj.is_folder else parent.documents
        session.delete(obj)
        collection.remove(obj)

    #
    # Locking (TODO)
    #
    def is_locked(self, obj):
        return False

    def can_unlock(self, obj):
        return True

    def lock(self, obj):
        return "???"

    def unlock(self, obj):
        pass

    #
    # Security / access rights
    #
    def has_permission(self, user, permission, obj):
        return security.has_permission(user, permission, obj, inherit=True)

    def has_access(self, user, obj):
        """
        Checks that user has actual right to reach this object, 'read' permission
        on each of object's parents.
        """
        current = obj
        while current.parent is not None:
            if not self.has_permission(user, READ, current):
                return False
            current = current.parent
        return True


repository = Repository()
