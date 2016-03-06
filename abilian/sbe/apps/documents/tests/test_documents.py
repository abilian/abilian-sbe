# coding=utf-8
"""
"""
from __future__ import absolute_import

import unittest
from cStringIO import StringIO
from itertools import count
from os.path import dirname, join
from zipfile import ZipFile

from flask import g, get_flashed_messages
from werkzeug.datastructures import FileStorage

from abilian.sbe.apps.communities.models import WRITER
from abilian.sbe.apps.communities.presenters import CommunityPresenter
from abilian.sbe.apps.communities.tests.base import (CommunityBaseTestCase,
                                                     CommunityIndexingTestCase)
from abilian.sbe.apps.documents.models import (Document, Folder,
                                               PathAndSecurityIndexable, db)
from abilian.sbe.apps.documents.views import util as view_util
from abilian.web.util import url_for


class BaseTests(CommunityBaseTestCase):
    init_data = True
    no_login = True

    def setUp(self):
        super(BaseTests, self).setUp()

        self.root_folder = Folder(title=u"root")
        db.session.add(self.root_folder)
        db.session.flush()

    @staticmethod
    def uid_from_url(url):
        return int(url.split("/")[-1])

    @staticmethod
    def open_file(filename):
        path = join(dirname(__file__), "data", "dummy_files", filename)
        return open(path, 'rb')


class TestBlobs(BaseTests):

    def test_document(self):
        root = Folder(title=u"root")
        doc = Document(parent=root, title=u"test")
        data = self.open_file("onepage.pdf").read()
        doc.set_content(data, "application/pdf")
        self.session.add(doc)
        self.session.commit()

        # coverage
        self.app.config['ANTIVIRUS_CHECK_REQUIRED'] = True
        doc.ensure_antivirus_scheduled()

    def test_antivirus_properties(self):
        root = Folder(title=u"root")
        doc = Document(parent=root, title=u"test")
        doc.set_content('content', 'text/plain')
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
        folder = Folder(title=u'Folder 1', parent=self.community.folder)
        self.session.add(folder)
        folder_other = Folder(title=u'Folder 2: other', parent=self.c2.folder)
        self.session.add(folder_other)
        self.session.commit()

        svc = self.svc
        obj_types = (Folder.entity_type,)
        with self.login(self.user_no_community):
            res = svc.search(u'folder', object_types=obj_types)
            assert len(res) == 0

        with self.login(self.user):
            res = svc.search(u'folder', object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit['object_key'] == folder.object_key
            assert hit['community_slug'] == self.community.slug

        with self.login(self.user_c2):
            res = svc.search(u'folder', object_types=obj_types)
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
            name = u'document'
            fs = FileStorage(
                StringIO(u'content'),
                filename=name,
                content_type='text/plain')
            doc = view_util.create_document(self.folder, fs)
            self.session.flush()
            assert doc.parent == self.folder
            assert doc.name == name

            # test upload with same name: should be renamed
            fs = FileStorage(
                StringIO(u'content'),
                filename=name,
                content_type='text/plain')
            doc2 = view_util.create_document(self.folder, fs)
            self.session.flush()
            assert doc2.parent == self.folder
            assert len(self.folder.children) == 2
            assert doc2.name == name + u'-1'
            messages = get_flashed_messages()
            assert len(messages) == 1

    def test_home(self):
        with self.client_login(self.user.email, password='azerty'):
            response = self.get(url_for('documents.index',
                                        community_id=self.community.slug))
            self.assert_status(response, 302)
            self.assertEquals(response.headers['Location'],
                              u'http://localhost/communities/{}/docs/folder/{}'
                              u''.format(self.community.slug, self.folder.id),)

    def _test_upload(self,
                     title,
                     content_type,
                     test_preview=True,
                     assert_preview_available=True):
        data = {
            'file': (self.open_file(title), title, content_type),
            'action': 'upload',
        }

        folder = self.community.folder
        url = url_for("documents.folder_post",
                      community_id=self.community.slug,
                      folder_id=folder.id)
        response = self.client.post(url, data=data)
        self.assert_status(response, 302)

        doc = folder.children[0]
        assert doc.title == title
        url = url_for("documents.document_view",
                      community_id=self.community.slug,
                      doc_id=doc.id)
        response = self.get(url)
        self.assert_200(response)

        url = url_for("documents.document_download",
                      community_id=self.community.slug,
                      doc_id=doc.id)
        response = self.get(url)
        self.assert_200(response)
        assert response.headers['Content-Type'] == content_type

        content = self.open_file(title).read()
        assert response.data == content

        if test_preview:
            url = url_for("documents.document_preview_image",
                          community_id=self.community.slug,
                          doc_id=doc.id,
                          size=500)
            response = self.get(url)
            if assert_preview_available:
                self.assert_200(response)
                assert response.headers['Content-Type'] == 'image/jpeg'
            else:
                # redirect to 'missing image'
                self.assert_302(response)
                assert response.headers['Cache-Control'] == 'no-cache'

        url = url_for("documents.document_delete",
                      community_id=self.community.slug,
                      doc_id=doc.id)
        response = self.client.post(url)
        self.assert_302(response)

        url = url_for("documents.document_view",
                      community_id=self.community.slug,
                      doc_id=doc.id)
        response = self.get(url)
        self.assert_404(response)

    def test_text_upload(self):
        NAME = 'wikipedia-fr.txt'
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(NAME, "text/plain", test_preview=False)

    def test_pdf_upload(self):
        NAME = u"onepage.pdf"
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(NAME, "application/pdf")

    def test_image_upload(self):
        NAME = u"picture.jpg"
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(NAME, "image/jpeg")

    def test_binary_upload(self):
        NAME = u"random.bin"
        with self.client_login(self.user.email, password='azerty'):
            self._test_upload(NAME,
                              "application/octet-stream",
                              assert_preview_available=False)

    def test_explore_archive(self):
        from abilian.sbe.apps.documents.views.folders import explore_archive
        fd = self.open_file('content.zip')
        result = [(u'/'.join(path), f)
                  for path, f in explore_archive(fd, u'content.zip')]
        assert result == [(u'', fd)]

        fd = self.open_file('content.zip')
        archive_content = explore_archive(fd, u'content.zip', uncompress=True)
        result = {u'/'.join(path) + u'/' + f.filename
                  for path, f in archive_content}
        assert result == {
            u'existing-doc/file.txt',
            u'existing-doc/subfolder_in_renamed/doc.txt', u'folder 1/doc.txt',
            u'folder 1/dos cp437: é.txt', u'folder 1/osx: utf-8: é.txt'
        }

    def test_zip_upload_uncompress(self):
        folder = Folder(title=u'folder 1', parent=self.community.folder)
        self.session.add(folder)
        self.session.flush()
        folder = self.community.folder
        files = []
        files.append((StringIO('A document'), u'existing-doc', 'text/plain'))
        files.append((self.open_file('content.zip'), u'content.zip',
                      'application/zip'))
        data = {'file': files, 'action': 'upload', 'uncompress_files': True}
        url = url_for("documents.folder_post",
                      community_id=self.community.slug,
                      folder_id=folder.id)
        with self.client_login(self.user.email, password='azerty'):
            response = self.client.post(url, data=data)

        expected = {u'existing-doc', u'folder 1', u'existing-doc-1'}
        self.assert_status(response, 302)
        assert expected == {f.title for f in folder.children}
        expected = {u'folder 1', u'existing-doc-1'}
        assert expected == {f.title for f in folder.subfolders}

    def test_zip(self):
        with self.client_login(self.user.email, password='azerty'):
            title = u"onepage.pdf"
            content_type = "application/pdf"
            data = {
                'file': (self.open_file(title), title, content_type),
                'action': 'upload',
            }
            folder = self.community.folder
            url = url_for("documents.folder_post",
                          community_id=self.community.slug,
                          folder_id=folder.id)
            response = self.client.post(url, data=data)
            self.assert_302(response)

            doc = folder.children[0]
            data = {'action': 'download',
                    'object-selected': ["cmis:document:%d" % doc.id]}
            url = url_for("documents.folder_post",
                          community_id=self.community.slug,
                          folder_id=folder.id)
            response = self.client.post(url, data=data)
            self.assert_200(response)
            assert response.content_type == 'application/zip'

            zipfile = ZipFile(StringIO(response.data))
            assert zipfile.namelist() == [title]

    def test_recursive_zip(self):
        with self.client_login(self.user.email, password='azerty'):
            data = {'action': 'new', 'title': u'my folder'}
            folder = self.community.folder
            url = url_for("documents.folder_post",
                          community_id=self.community.slug,
                          folder_id=folder.id)
            response = self.client.post(url, data=data)
            self.assert_302(response)

            my_folder = folder.children[0]

            title = u"onepage.pdf"
            content_type = "application/pdf"
            data = {
                'file': (self.open_file(title), title, content_type),
                'action': 'upload',
            }
            url = url_for("documents.folder_post",
                          community_id=self.community.slug,
                          folder_id=my_folder.id)
            response = self.client.post(url, data=data)
            self.assert_302(response)

            data = {'action': 'download',
                    'object-selected': ["cmis:folder:%d" % my_folder.id]}
            url = url_for("documents.folder_post",
                          community_id=self.community.slug,
                          folder_id=folder.id)
            response = self.client.post(url, data=data)
            self.assert_200(response)
            assert response.content_type == 'application/zip'

            zipfile = ZipFile(StringIO(response.data))
            assert zipfile.namelist() == ['my folder/' + title]

    def test_document_send_by_mail(self):
        mail = self.app.extensions['mail']
        folder = self.community.folder

        attachment = 'Content-Disposition: attachment; filename="{}"'.format
        attachment_utf8 = 'Content-Disposition: attachment;\n filename*="UTF8\'\'{}"'.format

        with self.client_login(self.user.email, password='azerty'):
            # upload files
            for filename in (u'ascii title.txt', u'utf-8 est arrivé!.txt'):
                content_type = "text/plain"
                data = {
                    'file': (StringIO('file content'), filename, content_type),
                    'action': 'upload',
                }
                url = url_for("documents.folder_post",
                              community_id=self.community.slug,
                              folder_id=folder.id)
                self.client.post(url, data=data)

            ascii_doc = folder.children[0]
            unicode_doc = folder.children[1]

            def get_send_url(doc_id):
                return url_for('documents.document_send',
                               community_id=self.community.slug,
                               doc_id=doc_id)

            # mail ascii filename
            with mail.record_messages() as outbox:
                url = get_send_url(ascii_doc.id)
                rv = self.client.post(url,
                                      data={'recipient': 'dest@example.com',
                                            'message': u'Voilà un fichier'})
                self.assertEquals(rv.status_code, 302,
                                  "expected 302, got:" + rv.status)
                assert len(outbox) == 1
                msg = outbox[0]
                self.assertEquals(msg.subject,
                                  u'[Abilian Test] Unknown sent you a file')
                assert msg.recipients == [u'dest@example.com']
                expected_disposition = attachment('ascii title.txt')
                msg = str(msg)
                assert expected_disposition in msg

            # mail unicode filename
            with mail.record_messages() as outbox:
                url = get_send_url(unicode_doc.id)
                rv = self.client.post(url,
                                      data={'recipient': 'dest@example.com',
                                            'message': u'Voilà un fichier'})
                assert rv.status_code == 302
                assert len(outbox) == 1
                msg = outbox[0]
                self.assertEquals(msg.subject,
                                  u'[Abilian Test] Unknown sent you a file')
                self.assertEquals(msg.recipients, [u'dest@example.com'])
                expected_disposition = attachment_utf8(
                    'utf-8%20est%20arriv%C3%A9%21.txt')
                msg = str(msg)
                self.assertTrue(expected_disposition in msg,
                                (expected_disposition, msg))


class TestPathIndexable(unittest.TestCase):

    class MockPath(PathAndSecurityIndexable):

        def __init__(self, id, parent=None):
            self.id = id
            self.parent = parent

    def setUp(self):
        id_gen = count()
        obj = self.MockPath(id_gen.next())
        obj = self.MockPath(id_gen.next(), parent=obj)
        obj = self.MockPath(id_gen.next(), parent=obj)
        self.obj = self.MockPath(id_gen.next(), parent=obj)

    def test_iter_to_root(self):
        assert [o.id for o in self.obj._iter_to_root()] == [3, 2, 1, 0]
        assert [o.id
                for o in self.obj._iter_to_root(skip_self=True)] == [2, 1, 0]

    def test_indexable_parent_ids(self):
        self.assertEquals(self.obj._indexable_parent_ids, u'/0/1/2')
