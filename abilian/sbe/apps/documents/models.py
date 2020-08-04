"""Entity objects for the Document Management applications.

TODO: move to an independent service / app.
"""
import itertools
import logging
import mimetypes
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Collection, Dict, Iterator, List, \
    Optional, Tuple, Union

import pkg_resources
import sqlalchemy as sa
import whoosh.fields as wf
from flask import current_app, json, url_for
from flask_login import current_user
from sqlalchemy.event import listen, listens_for
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, foreign, relationship, remote
from sqlalchemy.orm.attributes import Event
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import Integer, Text, UnicodeText
from sqlalchemy.util.langhelpers import symbol
from toolz import first
from whoosh.analysis import CharsetFilter, LowercaseFilter, RegexTokenizer
from whoosh.support.charset import accent_map

from abilian.core.entities import Entity, db
from abilian.core.models import NOT_AUDITABLE, SEARCHABLE
from abilian.core.models.blob import Blob
from abilian.core.models.subjects import Group, User
from abilian.core.util import md5
from abilian.services.conversion import converter
from abilian.services.indexing import indexable_role
from abilian.services.security import Admin, Anonymous, InheritSecurity, \
    security

from . import tasks
from .lock import Lock

if TYPE_CHECKING:
    from abilian.sbe.apps.communities.models import Community

logger = logging.getLogger(__package__)

__all__ = (
    "CmisObject",
    "Folder",
    "Document",
    "BaseContent",
    "PathAndSecurityIndexable",
    "icon_for",
    "icon_url",
    "setup_listener",
)

#: A Whoosh analyzer that folds accents and case.
accent_folder = RegexTokenizer() | LowercaseFilter() | CharsetFilter(accent_map)

ICONS_FOLDER = pkg_resources.resource_filename("abilian.sbe", "static/fileicons")


def icon_url(filename: str) -> str:
    return url_for("abilian_sbe_static", filename="fileicons/" + filename)


def icon_exists(filename: str) -> bool:
    return Path(ICONS_FOLDER, filename).is_file()


#
# Domain classes
#
class CmisObject(InheritSecurity, Entity):
    """(Abstract) Base class for CMIS objects."""

    # normally set by communities.models.community_content,
    # but we have to fix a circ.dep to use it
    is_community_content = True

    __tablename__ = "cmisobject"
    __indexable__ = False
    __index_to__ = (
        ("community.id", ("community_id",)),
        #
        ("community.slug", ("community_slug",)),
    )

    _title = Column("title", UnicodeText, nullable=False, default="")
    description = Column(
        UnicodeText,
        nullable=False,
        default="",
        info=SEARCHABLE | {"index_to": ("description", "text")},
    )

    _parent_id = Column(Integer, ForeignKey("cmisobject.id"), nullable=True)

    # no duplicate name in same folder
    __table_args__ = (UniqueConstraint("_parent_id", "title"),)

    # Set in concrete classes
    sbe_type: str = None

    # Convenience default values
    content_length = 0

    def __init__(self, *args, **kwargs):
        # ensure 'title' prevails over 'name'
        if "title" in kwargs and "name" in kwargs:
            title = kwargs.get("title")
            name = kwargs.get("name")

            if title is None:
                del kwargs["title"]
            elif name != title:
                kwargs["name"] = title

        Entity.__init__(self, *args, **kwargs)

    # title is defined has an hybrid property to allow 2 way sync name <->
    # title
    @hybrid_property
    def title(self: str) -> str:
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        # set title before setting name, so that we don't enter an infinite loop
        # with _cmis_sync_name_title
        self._title = title
        if self.name != title:
            self.name = title

    def clone(
        self, title: Optional[str] = None, parent: Optional["Folder"] = None
    ) -> "CmisObject":
        if not title:
            title = self.title
        new_obj = self.__class__(title=title, name=title, parent=parent)
        state = vars(self)
        for k, v in state.items():
            if not k.startswith("_") and k not in [
                "uid",
                "id",
                "parent",
                "title",
                "name",
                "path",
                "subfolders",
                "documents",
            ]:
                setattr(new_obj, k, v)
        if self.parent:
            assert self in self.parent.children
        return new_obj

    @property
    def path(self) -> str:
        if self.parent:
            return self.parent.path + "/" + self.title
        else:
            return ""

    @property
    def is_folder(self) -> bool:
        return self.sbe_type == "cmis:folder"

    @property
    def is_document(self) -> bool:
        return self.sbe_type == "cmis:document"

    @property
    def is_root_folder(self) -> bool:
        return self._parent_id is None

    @property
    def community(self) -> Optional["Community"]:
        if not self.is_folder:
            return self.parent and self.parent.community

        if self._community:
            return self._community

        return self.parent and self.parent.community


@listens_for(CmisObject.name, "set", propagate=True, active_history=True)
def _cmis_sync_name_title(
    entity: CmisObject, new_value: str, old_value: Union[symbol, str], initiator: Event
) -> str:
    """Synchronize CmisObject name -> title.

    CmisObject.title -> name is done via hybrid_property, avoiding
    infinite loop (since "set" is received before attribute has received
    value)
    """
    if entity.title != new_value:
        entity.title = new_value
    return new_value


class PathAndSecurityIndexable:
    """Mixin for folder and documents indexation."""

    __index_to__ = (
        ("_indexable_parent_ids", ("parent_ids",)),
        ("_indexable_roles_and_users", ("allowed_roles_and_users",)),
    )

    def _iter_to_root(
        self, skip_self: bool = False
    ) -> Iterator[Union["Document", "Folder"]]:
        obj = self if not skip_self else self.parent
        while obj:
            yield obj
            obj = obj.parent

    @property
    def _indexable_parent_ids(self) -> str:
        """Return a string made of ids separated by a slash: "/1/3/4/5", "5"
        being self.parent.id."""
        ids = [str(obj.id) for obj in self._iter_to_root(skip_self=True)]
        return "/" + "/".join(reversed(ids))

    @property
    def _indexable_roles_and_users(self) -> str:
        """Returns a string made of type:id elements, like "user:2 group:1
        user:6"."""
        iter_from_root = reversed(list(self._iter_to_root()))
        if self.parent:
            # skip root folder only on non-root folder!
            next(iter_from_root)
        allowed = {o[0] for o in security.get_role_assignements(next(iter_from_root))}

        for obj in iter_from_root:
            if obj.inherit_security:
                continue
            obj_allowed = {o[0] for o in security.get_role_assignements(obj)}

            if Anonymous in obj_allowed:
                continue

            parent_allowed = allowed
            # pure intersection: users and groups in both are preserved
            allowed = allowed & obj_allowed
            remaining = parent_allowed - obj_allowed
            # find users who can access 'obj' because of their group memberships
            # 1. extends groups in obj_allowed with their actual member list
            extended_allowed = set(
                itertools.chain(
                    *(p.members if isinstance(p, Group) else (p,) for p in obj_allowed)
                )
            )

            # 2. remaining_users are users explicitly listed in parents but not on
            # obj. Are they in a group?
            remaining_users = {o for o in remaining if isinstance(o, User)}
            allowed |= remaining_users & extended_allowed

            # remaining groups: find if some users are eligible
            remaining_groups_members = set(
                itertools.chain(*(p.members for p in remaining if isinstance(p, Group)))
            )
            allowed |= remaining_groups_members - extended_allowed

        # admin role is always granted access
        allowed.add(Admin)
        return " ".join(indexable_role(p) for p in allowed)


class Folder(PathAndSecurityIndexable, CmisObject):
    __tablename__: Optional[str] = None
    sbe_type = "cmis:folder"

    __indexable__ = True

    _indexable_roles_and_users = PathAndSecurityIndexable._indexable_roles_and_users

    parent = relationship(
        "Folder",
        primaryjoin=(lambda: foreign(CmisObject._parent_id) == remote(Folder.id)),
        backref=backref(
            "subfolders",
            lazy="joined",
            order_by="Folder.title",
            cascade="all, delete-orphan",
        ),
    )

    @property
    def icon(self):
        return icon_url("folder.png")

    @property
    def children(self) -> List[Union["Document", "Folder"]]:
        return self.subfolders + self.documents

    @property
    def document_count(self) -> int:
        count = len(self.documents)
        for f in self.subfolders:
            count += f.document_count
        return count

    @property
    def depth(self) -> int:
        if self.parent is None:
            return 0

        return self.parent.depth + 1

    def create_subfolder(self, title: str) -> "Folder":
        subfolder = Folder(title=title, parent=self)
        assert subfolder in self.children
        return subfolder

    def create_document(self, title: str) -> "Document":
        doc = Document(title=title, parent=self)
        assert doc.parent == self
        assert doc in self.children
        return doc

    def get_object_by_path(self, path: str) -> Union["Document", "Folder", None]:
        assert path.startswith("/")
        assert "//" not in path

        if path == "/":
            return self

        path_segments = path[1:].split("/")
        obj = self
        try:
            for name in path_segments[:]:
                obj = first(x for x in obj.children if x.title == name)
            return obj
        except IndexError:
            return None

    def __repr__(self):
        return "<{}.{} id={!r} name={!r} path={!r} at 0x{:x}>".format(
            self.__class__.__module__,
            self.__class__.__name__,
            self.id,
            self.title,
            self.path,
            id(self),
        )

    #
    # Security related methods
    #
    @property
    def filtered_children(self) -> List[Union["Folder", "Document"]]:
        return security.filter_with_permission(
            current_user, "read", self.children, inherit=True
        )

    @property
    def filtered_subfolders(self) -> List["Folder"]:
        return security.filter_with_permission(
            current_user, "read", self.subfolders, inherit=True
        )

    def get_local_roles_assignments(self):
        local_roles_assignments = security.get_role_assignements(self)
        # local_roles_assignments = sorted(local_roles_assignments,
        #                                  key=lambda u: (u[0].last_name.lower(),
        #                                                 u[0].first_name.lower()))
        return local_roles_assignments

    def get_inherited_roles_assignments(self):
        if self.parent.is_root_folder:
            return []

        roles = self.parent.get_local_roles_assignments()
        inherited_roles = (
            self.parent.get_inherited_roles_assignments()
            if self.parent.inherit_security
            else []
        )

        assignments = set(itertools.chain(roles, inherited_roles))

        def key(x):
            principal = x[0]
            if isinstance(principal, User):
                # Defensive programming here, this shouldn't happen actually
                last_name = principal.last_name or ""
                first_name = principal.first_name or ""
                return last_name.lower(), first_name.lower()
            elif isinstance(principal, Group):
                return principal.name
            else:
                raise Exception(f"Bad class here: {type(principal)}")

        return sorted(assignments, key=key)

    def members(self) -> Collection[User]:
        local_roles = self.get_local_roles_assignments()
        inherited_roles = (
            self.get_inherited_roles_assignments() if self.inherit_security else []
        )

        def _iter_users(roles):
            for principal, _user in roles:
                if isinstance(principal, User):
                    yield principal
                else:
                    yield from itertools.chain(principal.members, principal.admins)

        members = set(_iter_users(itertools.chain(local_roles, inherited_roles)))
        members = sorted(members, key=lambda u: (u.last_name, u.first_name))
        return members


class BaseContent(CmisObject):
    """A base class for cmisobject with an attached file."""

    __tablename__: Optional[str] = None

    _content_id = Column(Integer, db.ForeignKey(Blob.id))
    content_blob = relationship(Blob, cascade="all, delete", foreign_keys=[_content_id])

    #: md5 digest (BTW: not sure they should be part of the public API).
    content_digest = Column(Text)

    #: size (in bytes) of the content blob.
    content_length = Column(
        Integer,
        default=0,
        nullable=False,
        server_default=sa.text("0"),
        info={
            "searchable": True,
            "index_to": (("content_length", wf.NUMERIC(stored=True)),),
        },
    )

    #: MIME type of the content stream.
    # TODO: normalize mime type?
    content_type = Column(
        Text,
        default="application/octet-stream",
        info={"searchable": True, "index_to": (("content_type", wf.ID(stored=True)),)},
    )

    @property
    def content(self) -> bytes:
        return self.content_blob.value

    @content.setter
    def content(self, value: bytes) -> None:
        assert isinstance(value, bytes)
        self.content_blob = Blob()
        self.content_blob.value = value
        self.content_length = len(value)

    def set_content(self, content: bytes, content_type: str = "") -> None:
        assert isinstance(content_type, str)

        new_digest = md5(content)
        if new_digest == self.content_digest:
            return

        self.content_digest = new_digest
        self.content = content
        content_type = self.find_content_type(content_type)
        if content_type:
            self.content_type = content_type

    def find_content_type(self, content_type: str = "") -> str:
        """Find possibly more appropriate content_type for this instance.

        If `content_type` is a binary one, try to find a better one
        based on content name so that 'xxx.pdf' is not flagged as
        binary/octet-stream for example
        """
        assert isinstance(content_type, str)

        if content_type not in (
            "",
            "application/octet-stream",
            "binary/octet-stream",
            "application/binary",
            "multipart/octet-stream",
        ):
            return content_type

        # missing or generic content type: try to find something more useful to be
        # able to do preview/indexing/...
        if self.title:
            guessed_content_type = mimetypes.guess_type(self.title, strict=False)[0]
            if (
                guessed_content_type
                and guessed_content_type != "application/vnd.ms-office.activeX"
            ):
                # mimetypes got an update: "random.bin" would be guessed as
                # 'application/vnd.ms-office.activeX'... not so useful in a document
                # repository
                content_type = guessed_content_type

        return content_type

    @property
    def icon(self) -> str:
        return icon_for(self.content_type)


class Document(BaseContent, PathAndSecurityIndexable):
    """A document, in the CMIS sense."""

    __tablename__: Optional[str] = None

    __indexable__ = True
    __index_to__ = (("text", ("text",)),)

    _indexable_roles_and_users = PathAndSecurityIndexable._indexable_roles_and_users

    parent = relationship(
        "Folder",
        primaryjoin=(foreign(CmisObject._parent_id) == remote(Folder.id)),
        backref=backref(
            "documents",
            lazy="joined",
            order_by="Document.title",
            cascade="all, delete-orphan",
        ),
    )

    PREVIEW_SIZE = 700

    @property
    def preview_size(self) -> int:
        return self.PREVIEW_SIZE

    def has_preview(self, size: int = 0, index: int = 0) -> bool:
        if size == 0:
            size = self.PREVIEW_SIZE

        return converter.has_image(self.content_digest, self.content_type, index, size)

    @property
    def digest(self) -> str:
        """Alias for content_digest."""
        return self.content_digest

    _text_id = Column(Integer, db.ForeignKey(Blob.id), info=NOT_AUDITABLE)
    text_blob = relationship(Blob, cascade="all, delete", foreign_keys=[_text_id])

    _pdf_id = Column(Integer, db.ForeignKey(Blob.id), info=NOT_AUDITABLE)
    pdf_blob = relationship(Blob, cascade="all, delete", foreign_keys=[_pdf_id])

    _preview_id = Column(Integer, db.ForeignKey(Blob.id), info=NOT_AUDITABLE)
    preview_blob = relationship(Blob, cascade="all, delete", foreign_keys=[_preview_id])

    language = Column(
        Text, info={"searchable": True, "index_to": [("language", wf.ID(stored=True))]}
    )
    size = Column(Integer)
    page_num = Column(Integer, default=1)

    # FIXME: use Entity.meta instead
    #: Stores extra metadata as a JSON column
    extra_metadata_json = Column(UnicodeText, info={"auditable": False})

    sbe_type = "cmis:document"

    # antivirus status
    def ensure_antivirus_scheduled(self) -> bool:
        if not self.antivirus_required:
            return True

        if current_app.config.get("CELERY_ALWAYS_EAGER", False):
            async_conversion(self)
            return True

        task_id = self.content_blob.meta.get("antivirus_task_id")
        if task_id is not None:
            res = tasks.process_document.AsyncResult(task_id)
            if not res.failed():
                # success, or pending or running
                return True

        # schedule a new task
        self.content_blob.meta["antivirus_task_id"] = str(uuid.uuid4())
        async_conversion(self)
        return False

    @property
    def antivirus_scanned(self) -> bool:
        """True if antivirus task was run, even if antivirus didn't return a
        result."""
        return self.content_blob and "antivirus" in self.content_blob.meta

    @property
    def antivirus_status(self) -> Optional[bool]:
        """
        True: antivirus has scanned file: no virus
        False: antivirus has scanned file: virus detected
        None: antivirus task was run, but antivirus didn't return a result
        """
        return self.content_blob and self.content_blob.meta.get("antivirus")

    @property
    def antivirus_required(self) -> bool:
        """True if antivirus doesn't need to be run."""
        required = current_app.config["ANTIVIRUS_CHECK_REQUIRED"]
        return required and (
            not self.antivirus_scanned or self.antivirus_status is None
        )

    @property
    def antivirus_ok(self) -> bool:
        """True if user can safely access document content."""
        required = current_app.config["ANTIVIRUS_CHECK_REQUIRED"]
        if required:
            return self.antivirus_status is True

        return self.antivirus_status is not False

    # R/W properties
    @BaseContent.content.setter
    def content(self, value: bytes) -> None:
        BaseContent.content.fset(self, value)
        self.content_blob.meta["antivirus_task_id"] = str(uuid.uuid4())
        self.pdf_blob = None
        self.text_blob = None

    def set_content(self, content: bytes, content_type: str = "") -> None:
        super().set_content(content, content_type)
        async_conversion(self)

    @property
    def pdf(self):
        if self.pdf_blob:
            assert isinstance(self.pdf_blob.value, bytes)
        return self.pdf_blob and self.pdf_blob.value

    @pdf.setter
    def pdf(self, value: bytes) -> None:
        assert isinstance(value, bytes)
        self.pdf_blob = Blob()
        self.pdf_blob.value = value

    # `text` is an Unicode value.
    @property
    def text(self) -> str:
        return self.text_blob.value.decode("utf8") if self.text_blob is not None else ""

    @text.setter
    def text(self, value: str) -> None:
        assert isinstance(value, str)
        self.text_blob = Blob()
        self.text_blob.value = value.encode("utf8")

    @property
    def extra_metadata(self) -> Dict[str, Any]:
        if not hasattr(self, "_extra_metadata"):
            if self._extra_metadata is not None:
                self._extra_metadata = json.loads(self.extra_metadata_json)
            else:
                self._extra_metadata = None
        return self._extra_metadata

    @extra_metadata.setter
    def extra_metadata(self, extra_metadata: Dict[str, Any]) -> None:
        self._extra_metadata = extra_metadata
        self.extra_metadata_json = str(json.dumps(extra_metadata))

    # TODO: or use SQLAlchemy alias?
    @property
    def file_name(self) -> str:
        return self.title

    def __repr__(self):
        return "<Document id={!r} name={!r} path={!r} content_length={:d} at 0x{:x}>".format(
            self.id, self.title, self.path, self.content_length, id(self)
        )

    # locking management; used for checkin/checkout - this could be generalized to
    # any entity
    @property
    def lock(self) -> Optional[Lock]:
        """
        :returns: either `None` if no lock or current lock is expired; either the
        current valid :class:`Lock` instance.
        """
        lock = self.meta.setdefault("abilian.sbe.documents", {}).get("lock")
        if lock:
            lock = Lock(**lock)
            if lock.expired:
                lock = None

        return lock

    @lock.setter
    def lock(self, user):
        """Allow to do `document.lock = user` to set a lock for user.

        If user is None, the lock is released.
        """
        if user is None:
            del self.lock
            return

        self.set_lock(user=user)

    @lock.deleter
    def lock(self):
        """Remove lock, if any.

        `del document.lock` can be safely done even if no lock is set.
        """
        meta = self.meta.setdefault("abilian.sbe.documents", {})
        if "lock" in meta:
            del meta["lock"]
            self.meta.changed()

    def set_lock(self, user=None):
        if user is None:
            user = current_user

        lock = self.lock
        if lock and not lock.is_owner(user=user):
            raise RuntimeError("This document is already locked by another user")

        meta = self.meta.setdefault("abilian.sbe.documents", {})
        lock = Lock.new()
        meta["lock"] = lock.as_dict()
        self.meta.changed()


def icon_for(content_type: str) -> str:
    for extension, mime_type in mimetypes.types_map.items():
        if mime_type == content_type:
            extension = extension[1:]
            icon = f"{extension}.png"
            if icon_exists(icon):
                return icon_url(icon)

    return icon_url("bin.png")


# Async conversion
_async_data = threading.local()


def _get_documents_queue() -> List[Tuple[Document, str]]:
    if not hasattr(_async_data, "documents"):
        _async_data.documents = []
    return _async_data.documents


def async_conversion(document: Document) -> None:
    _get_documents_queue().append(
        (document, document.content_blob.meta.get("antivirus_task_id"))
    )


def _trigger_conversion_tasks(session: Session) -> None:
    if (
        # this commit is not from the application session
        session is not db.session()
        # inside a sub-transaction: not yet written in DB
        or session.transaction.nested
    ):
        return

    document_queue = _get_documents_queue()
    while document_queue:
        doc, task_id = document_queue.pop()
        if doc.id:
            tasks.process_document.apply_async((doc.id,), task_id=task_id)


def setup_listener() -> None:
    mark_attr = "__abilian_sa_listening"
    if getattr(_trigger_conversion_tasks, mark_attr, False):
        return

    listen(Session, "after_commit", _trigger_conversion_tasks)
    setattr(_trigger_conversion_tasks, mark_attr, True)
