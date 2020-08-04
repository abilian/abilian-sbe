from typing import Any, Dict

from flask import Blueprint as BaseBlueprint
from flask import g
from werkzeug.exceptions import NotFound

from abilian.i18n import _l
from abilian.web.action import Endpoint
from abilian.web.nav import BreadcrumbItem

from . import security
from .models import Community
from .presenters import CommunityPresenter


class Blueprint(BaseBlueprint):
    """Blueprint for community based views.

    It sets g.community and perform access verification for the
    traversed community.
    """

    _BASE_URL_PREFIX = "/communities"
    _ROUTE_PARAM = "<string:community_id>"

    def __init__(self, *args: str, **kwargs: Any) -> None:
        url_prefix = kwargs.get("url_prefix", "")

        if kwargs.pop("set_community_id_prefix", True):
            if (not url_prefix) or url_prefix[0] != "/":
                url_prefix = "/" + url_prefix
            url_prefix = self._ROUTE_PARAM + url_prefix

        if not url_prefix.startswith(self._BASE_URL_PREFIX):
            if (not url_prefix) or url_prefix[0] != "/":
                url_prefix = "/" + url_prefix
            url_prefix = self._BASE_URL_PREFIX + url_prefix

        if url_prefix[-1] == "/":
            url_prefix = url_prefix[:-1]
        kwargs["url_prefix"] = url_prefix

        BaseBlueprint.__init__(self, *args, **kwargs)
        self.url_value_preprocessor(pull_community)
        self.url_value_preprocessor(init_current_tab)
        self.before_request(check_access)


def check_access() -> None:
    if hasattr(g, "community"):
        # communities.index is not inside a community, for example
        security.check_access(g.community)


def init_current_tab(endpoint: str, values: Dict[str, int]) -> None:
    """Ensure g.current_tab exists."""
    g.current_tab = None


def pull_community(endpoint: str, values: Dict[str, Any]) -> None:
    """url_value_preprocessor function."""
    g.nav["active"] = "section:communities"
    g.breadcrumb.append(
        BreadcrumbItem(label=_l("Communities"), url=Endpoint("communities.index"))
    )

    try:
        slug = values.pop("community_id")
        community = Community.query.filter(Community.slug == slug).first()
        if community:
            g.community = CommunityPresenter(community)
            wall_url = Endpoint("wall.index", community_id=community.slug)
            breadcrumb_item = BreadcrumbItem(label=community.name, url=wall_url)
            g.breadcrumb.append(breadcrumb_item)
        else:
            raise NotFound()
    except KeyError:
        pass
