"""Lightweight integration and denormalisation using events (signals)."""

from typing import Any, Optional

from blinker import ANY
from werkzeug.local import LocalProxy

from abilian.core.entities import Entity
from abilian.core.models.subjects import User
from abilian.core.signals import activity
from abilian.sbe.apps.communities.presenters import CommunityPresenter
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.wiki.models import WikiPage

from .models import Community


@activity.connect_via(ANY)
def update_community(
    sender: Any, verb: str, actor: User, object: Entity, target: Optional[Entity] = None
) -> None:
    if isinstance(object, Community):
        object.touch()
        return

    if isinstance(target, Community):
        community = target
        community.touch()

        if isinstance(object, Document):
            if verb == "post":
                community.document_count += 1
            elif verb == "delete":
                community.document_count -= 1
