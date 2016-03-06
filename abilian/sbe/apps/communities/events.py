# coding=utf-8
"""
Lightweight integration and denormalisation using events (signals).
"""

from __future__ import absolute_import

from blinker import ANY

from abilian.core.signals import activity
from abilian.sbe.apps.documents.models import Document

from .models import Community


@activity.connect_via(ANY)
def update_community(sender, verb, actor, object, target=None):
    if isinstance(object, Community):
        object.touch()
        return

    if isinstance(target, Community):
        community = target
        community.touch()

        if isinstance(object, Document):
            if verb == 'post':
                community.document_count += 1
            elif verb == 'delete':
                community.document_count -= 1
