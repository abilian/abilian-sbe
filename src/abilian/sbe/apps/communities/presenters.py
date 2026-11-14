# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from abilian.core.util import BasePresenter
from abilian.i18n import _l


class CommunityPresenter(BasePresenter):
    @property
    def breadcrumbs(self):
        return [
            {"label": _l("Communities"), "path": "/communities/"},
            {"label": self._model.name},
        ]
