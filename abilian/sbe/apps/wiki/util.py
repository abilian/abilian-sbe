from __future__ import absolute_import, print_function, unicode_literals

from flask import g


def page_exists(title):
    from abilian.sbe.apps.wiki.models import WikiPage

    title = title.strip()
    return (
        WikiPage.query.filter(
            WikiPage.community_id == g.community.id, WikiPage.title == title
        ).count()
        > 0
    )
