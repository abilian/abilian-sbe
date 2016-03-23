# coding=utf-8
"""
"""
from __future__ import absolute_import

import logging
import uuid

import pkg_resources
from pathlib import Path

from abilian.core.util import fqcn

logger = logging.getLogger(__name__)
STATIC_DIR = pkg_resources.resource_filename(__name__, 'static')
LESSCSS_FILE = str(Path(STATIC_DIR, 'less', 'abilian-sbe.less'))
JS = ('js/sbe-datatable.js',
      'js/jquery.fileapi.js',
      'js/folder.js',
      'js/folder_edit.js',
      'js/folder_upload.js',
      'js/document_viewer.js',)


class AbilianSBE(object):
    """
    Base extension required by abilian.sbe.apps
    """

    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        # False: it's ok if antivirus task was run but service couldn't get a result
        app.config.setdefault('ANTIVIRUS_CHECK_REQUIRED', False)
        app.config.setdefault('SBE_FORUM_REPLY_BY_MAIL', False)

        if FQCN in app.extensions:
            return

        app.extensions[FQCN] = self

        # register i18n
        app.extensions['babel'].add_translations('abilian.sbe')

        # sbe static assets
        app.add_static_url('abilian/sbe',
                           STATIC_DIR,
                           endpoint='abilian_sbe_static')
        app.extensions['webassets'].append_path(
            STATIC_DIR, app.static_url_path + '/abilian/sbe')

        app.register_asset('js', *JS)
        app.register_asset('css', LESSCSS_FILE)
        logger.info('Register jinja context processors')
        app.context_processor(inject_template_utils)


FQCN = fqcn(AbilianSBE)
sbe = AbilianSBE()


def inject_template_utils():
    return dict(uuid=uuid.uuid1)
