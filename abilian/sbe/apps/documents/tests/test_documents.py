# coding=utf-8
""""""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

import sys
import unittest
from io import BytesIO
from itertools import count
from pathlib import Path
from zipfile import ZipFile

import flask_mail
import pytest
from abilian.web.util import url_for
from flask import g, get_flashed_messages
from toolz import first
from werkzeug.datastructures import FileStorage

from abilian.sbe.apps.communities.models import WRITER
from abilian.sbe.apps.communities.presenters import CommunityPresenter
from abilian.sbe.apps.communities.tests.base import CommunityBaseTestCase, \
    CommunityIndexingTestCase

from ..models import Document, Folder, PathAndSecurityIndexable, db
from ..views import util as view_util
from ..views.folders import explore_archive


class BaseTests(CommunityBaseTestCase):
    no_login = True

    def setUp(self):
        super(BaseTests, self).setUp()

        self.root_folder = Folder(title="root")
        db.session.add(self.root_folder)
        db.session.flush()

    @staticmethod
    def uid_from_url(url):
        return int(url.split("/")[-1])

    @staticmethod
    def open_file(filename):
        path = Path(__file__).parent / "data" / "dummy_files" / filename
        return path.open('rb')


class TestBlobs(BaseTests):
    def test_document(self):
        root = Folder(title="root")
        doc = Document(parent=root, title="test")
        data = self.open_file("onepage.pdf").read()
        doc.set_content(data, "application/pdf")
        self.session.add(doc)
        self.session.commit()

        # coverage
        self.app.config['ANTIVIRUS_CHECK_REQUIRED'] = True
        doc.ensure_antivirus_scheduled()

    def test_antivirus_properties(self):
        root = Folder(title="root")
        doc = Document(parent=root, title="test")
        doc.set_content(b'content', 'text/plain')
        appcfg = self.app.config
        meta = doc.content_blob.meta

        # 1: not check required ################
        # no data in meta
        appcfg['ANTIVIRUS_CHECK_REQUIRED'] = False
        assert doc.antivirus_scanned is False
        assert doc.antivirus_status is None
        assert doc.antivirus_required is False
        assert doc.antivirus_ok is True

        # antivirus was run, but no result
        meta['antivirus'] = None
        assert doc.antivirus_scanned is True
        assert doc.antivirus_status is None
        assert doc.antivirus_required is False
        assert doc.antivirus_ok is True

        # virus detected
        meta['antivirus'] = False
        assert doc.antivirus_scanned is True
        assert doc.antivirus_status is False
        assert doc.antivirus_required is False
        assert doc.antivirus_ok is False

        # virus free
        meta['antivirus'] = True
        assert doc.antivirus_scanned is True
        assert doc.antivirus_status is True
        assert doc.antivirus_required is False
        assert doc.antivirus_ok is True

        # 2: check required ##################
        # no data in meta
        del meta['antivirus']
        appcfg['ANTIVIRUS_CHECK_REQUIRED'] = True
        assert doc.antivirus_scanned is False
        assert doc.antivirus_status is None
        assert doc.antivirus_required is True
        assert doc.antivirus_ok is False

        # antivirus was run, but no result
        meta['antivirus'] = None
        assert doc.antivirus_scanned is True
        assert doc.antivirus_status is None
        assert doc.antivirus_required is True
        assert doc.antivirus_ok is False

        # virus detected
        meta['antivirus'] = False
        assert doc.antivirus_scanned is True
        assert doc.antivirus_status is False
        assert doc.antivirus_required is False
        assert doc.antivirus_ok is False

        # virus free
        meta['antivirus'] = True
        assert doc.antivirus_scanned is True
        assert doc.antivirus_status is True
        assert doc.antivirus_required is False
        assert doc.antivirus_ok is True


class IndexingTestCase(CommunityIndexingTestCase):
    def test_folder_indexed(self):
        folder = Folder(title='Folder 1', parent=self.community.folder)
        self.session.add(folder)
        folder_other = Folder(title='Folder 2: other', parent=self.c2.folder)
        self.session.add(folder_other)
        self.session.commit()

        svc = self.svc
        obj_types = (Folder.entity_type, )
        with self.login(self.user_no_community):
            res = svc.search('folder', object_types=obj_types)
            assert len(res) == 0

        with self.login(self.user):
            res = svc.search('folder', object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit['object_key'] == folder.object_key
            assert hit['community_slug'] == self.community.slug

        with self.login(self.user_c2):
            res = svc.search('folder', object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit['object_key'] == folder_other.object_key
            assert hit['community_slug'] == self.c2.slug


class TestViews(CommunityIndexingTestCase, BaseTests):
    def setUp(self):
        super(TestViews, self).setUp()
        self.community.type = 'participative'
        self.community.set_membership(self.user, WRITER)
        self.session.commit()
        self.folder = self.community.folder

    def test_util_create(self):
        with self.login(self.user):
            g.user = self.user
            g.community = CommunityPresenter(self.community)
            name = 'document'
            fs = FileStorage(
                BytesIO(b'content'),
                filename=name,
                content_type='text/plain',
            )
            doc = view_util.create_document(self.folder, fs)
            self.session.flush()
            assert doc.parent == self.folder
            assert doc.name == name

            # test upload with same name: should be renamed
            fs = FileStorage(
                BytesIO(b'content'),
                filename=name,
                content_type='text/plain',
            )
            doc2 = view_util.create_document(self.folder, fs)
            self.session.flush()
            assert doc2.parent == self.folder
            assert len(self.folder.children) == 2
            assert doc2.name == name + '-1'

            messages = get_flashed_messages()
            assert len(messages) == 1

    def test_home(self):
        with self.client_login(self.user.email, password='azerty'):
            response = self.get(
                url_for('documents.index', community_id=self.community.slug),
            )
            assert response.status_code == 302
            expected = 'http://localhost/communities/{}/docs/folder/{}' \
                       ''.format(self.community.slug, self.folder.id)
            assert response.headers['Location'] == expected

    def _test_upload(
        self,
        title,
        content_type,
        test_preview=True,
        assert_preview_available=True,
    ):
        data = {
            'file': (self.open_file(title), title, content_type),
            'action': 'upload',
        }

        folder = self.community.folder
        url = url_for(
            "documents.folder_post",
            community_id=self.community.slug,
            folder_id=folder.id,
        )
        response = self.client.post(url, data=data)
        assert response.status_code == 302

        doc = folder.children[0]
        assert doc.title == title

        url = url_for(
            "documents.document_view",
            community_id=self.community.slug,
            doc_id=doc.id,
        )
        response = self.get(url)
        assert response.status_code == 200

        url = url_for(
            "documents.document_download",
            community_id=self.community.slug,
            doc_id=doc.id,
        )
        response = self.get(url)
        assert response.status_code == 200
        assert response.headers['Content-Type'] == content_type

        content = self.open_file(title).read()
        assert response.data == content

        if test_preview:
            url = url_for(
                "documents.document_preview_image",
                community_id=self.community.slug,
                doc_id=doc.id,
                size=500,
            )
            response = self.get(url)
            if assert_preview_available:
                assert response.status_code == 200
                assert response.headers['Content-Type'] == 'image/jpeg'
            else:
                # redirect to 'missing image'
                assert response.status_code == 302
                assert response.headers['Cache-Control'] == 'no-cache'

        url = url_for(
            "documents.document_delete",
            community_id=self.community.slug,
            doc_id=doc.id,
        )
        response = self.client.post(url)
        assert response.status_code == 302

        url = url_for(
            "documents.document_view",
            community_id=self.community.slug,
            doc_id=doc.id,
        )
        response = self.get(url)
        assert response.status_code == 404

    def test_text_upload(self):
        name = 'wikipedia-fr.txt'
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(name, "text/plain", test_preview=False)

    def test_pdf_upload(self):
        name = "onepage.pdf"
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(name, "application/pdf")

    def test_image_upload(self):
        NAME = "picture.jpg"
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(NAME, "image/jpeg")

    @pytest.mark.skip()  # FIXME: magic detection mismatch?
    def test_binary_upload(self):
        NAME = "random.bin"
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(
                NAME,
                "application/octet-stream",
                assert_preview_available=False,
            )

    @pytest.mark.skipif(
        sys.version_info >= (3, 0),
        reason="Doesn't work yet on Py3k",
    )
    def test_explore_archive(self):
        fd = self.open_file('content.zip')
        result = [('/'.join(path), f) for path, f in explore_archive(fd)]
        assert result == [('', fd)]

        fd = self.open_file('content.zip')
        archive_content = explore_archive(fd, uncompress=True)
        result = {
            '/'.join(path) + '/' + f.filename
            for path, f in archive_content
        }
        assert result == {
            'existing-doc/file.txt',
            'existing-doc/subfolder_in_renamed/doc.txt',
            'folder 1/doc.txt',
            'folder 1/dos cp437: é.txt',
            'folder 1/osx: utf-8: é.txt',
        }

    def test_zip_upload_uncompress(self):
        folder = Folder(title='folder 1', parent=self.community.folder)
        self.session.add(folder)
        self.session.flush()
        folder = self.community.folder
        files = []
        files.append((BytesIO(b'A document'), 'existing-doc', 'text/plain'))
        files.append((
            self.open_file('content.zip'),
            'content.zip',
            'application/zip',
        ))
        data = {'file': files, 'action': 'upload', 'uncompress_files': True}
        url = url_for(
            "documents.folder_post",
            community_id=self.community.slug,
            folder_id=folder.id,
        )
        with self.client_login(self.user.email, password='azerty'):
            response = self.client.post(url, data=data)

        assert response.status_code == 302
        expected = {'existing-doc', 'folder 1', 'existing-doc-1'}
        assert expected == {f.title for f in folder.children}
        expected = {'folder 1', 'existing-doc-1'}
        assert expected == {f.title for f in folder.subfolders}

    def test_zip(self):
        with self.client_login(self.user.email, password='azerty'):
            title = "onepage.pdf"
            content_type = "application/pdf"
            data = {
                'file': (self.open_file(title), title, content_type),
                'action': 'upload',
            }
            folder = self.community.folder
            url = url_for(
                "documents.folder_post",
                community_id=self.community.slug,
                folder_id=folder.id,
            )
            response = self.client.post(url, data=data)
            assert response.status_code == 302

            doc = folder.children[0]
            data = {
                'action': 'download',
                'object-selected': ["cmis:document:%d" % doc.id],
            }
            url = url_for(
                "documents.folder_post",
                community_id=self.community.slug,
                folder_id=folder.id,
            )
            response = self.client.post(url, data=data)
            assert response.status_code == 200
            assert response.content_type == 'application/zip'

            zipfile = ZipFile(BytesIO(response.data))
            assert [zipfile.namelist()[0]] == [title]

    def test_recursive_zip(self):
        with self.client_login(self.user.email, password='azerty'):
            data = {
                'action': 'new',
                'title': 'my folder',
            }
            folder = self.community.folder
            url = url_for(
                "documents.folder_post",
                community_id=self.community.slug,
                folder_id=folder.id,
            )
            response = self.client.post(url, data=data)
            assert response.status_code == 302

            my_folder = folder.children[0]

            title = "onepage.pdf"
            content_type = "application/pdf"
            data = {
                'file': (self.open_file(title), title, content_type),
                'action': 'upload',
            }
            url = url_for(
                "documents.folder_post",
                community_id=self.community.slug,
                folder_id=my_folder.id,
            )
            response = self.client.post(url, data=data)
            assert response.status_code == 302

            data = {
                'action': 'download',
                'object-selected': ["cmis:folder:%d" % my_folder.id],
            }
            url = url_for(
                "documents.folder_post",
                community_id=self.community.slug,
                folder_id=folder.id,
            )
            response = self.client.post(url, data=data)
            assert response.status_code == 200
            assert response.content_type == 'application/zip'

            zipfile = ZipFile(BytesIO(response.data))
            assert zipfile.namelist() == ['my folder/' + title]

    def test_document_send_by_mail(self):
        mail = self.app.extensions['mail']
        folder = self.community.folder

        with self.client_login(self.user.email, password='azerty'):
            # upload files
            for filename in ('ascii title.txt', 'utf-8 est arrivé!.txt'):
                content_type = "text/plain"
                data = {
                    'file': (BytesIO(b'file content'), filename, content_type),
                    'action': 'upload',
                }
                url = url_for(
                    "documents.folder_post",
                    community_id=self.community.slug,
                    folder_id=folder.id,
                )
                self.client.post(url, data=data)

            ascii_doc = folder.children[0]
            unicode_doc = folder.children[1]

            def get_send_url(doc_id):
                return url_for(
                    'documents.document_send',
                    community_id=self.community.slug,
                    doc_id=doc_id,
                )

            # mail ascii filename
            with mail.record_messages() as outbox:
                url = get_send_url(ascii_doc.id)
                response = self.client.post(
                    url,
                    data={
                        'recipient': 'dest@example.com',
                        'message': 'Voilà un fichier',
                    },
                )
                assert response.status_code == 302
                assert len(outbox) == 1

                msg = outbox[0]
                assert msg.subject == '[Abilian Test] Unknown sent you a file'
                assert msg.recipients == ['dest@example.com']

                assert len(msg.attachments) == 1

                attachment = first(msg.attachments)
                assert isinstance(attachment, flask_mail.Attachment)
                assert attachment.filename == "ascii title.txt"

            # mail unicode filename
            with mail.record_messages() as outbox:
                url = get_send_url(unicode_doc.id)
                response = self.client.post(
                    url,
                    data={
                        'recipient': 'dest@example.com',
                        'message': 'Voilà un fichier',
                    },
                )
                assert response.status_code == 302
                assert len(outbox) == 1

                msg = outbox[0]
                assert isinstance(msg, flask_mail.Message)
                assert msg.subject == '[Abilian Test] Unknown sent you a file'
                assert msg.recipients == ['dest@example.com']
                assert len(msg.attachments) == 1

                attachment = first(msg.attachments)
                assert isinstance(attachment, flask_mail.Attachment)
                assert attachment.filename == "utf-8 est arrivé!.txt"


class TestPathIndexable(unittest.TestCase):
    class MockPath(PathAndSecurityIndexable):
        def __init__(self, id, parent=None):
            self.id = id
            self.parent = parent

    def setUp(self):
        id_gen = count()
        obj = self.MockPath(next(id_gen))
        obj = self.MockPath(next(id_gen), parent=obj)
        obj = self.MockPath(next(id_gen), parent=obj)
        self.obj = self.MockPath(next(id_gen), parent=obj)

    def test_iter_to_root(self):
        assert [o.id for o in self.obj._iter_to_root()] == [3, 2, 1, 0]
        assert [o.id for o in self.obj._iter_to_root(skip_self=True)] == [
            2,
            1,
            0,
        ]

    def test_indexable_parent_ids(self):
        assert self.obj._indexable_parent_ids == '/0/1/2'
