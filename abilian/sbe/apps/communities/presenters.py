# coding=utf-8
from abilian.core.util import BasePresenter
from flask_babel import lazy_gettext as _l


class CommunityPresenter(BasePresenter):
    @property
    def breadcrumbs(self):
        return [
            {"label": _l("Communities"), "path": "/communities/"},
            {"label": self._model.name},
        ]
