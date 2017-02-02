from __future__ import absolute_import, print_function

from flask_babel import lazy_gettext as _l

from abilian.core.util import BasePresenter


class CommunityPresenter(BasePresenter):

    @property
    def breadcrumbs(self):
        return [
            dict(label=_l("Communities"), path="/communities/"),
            dict(label=self._model.name)
        ]
