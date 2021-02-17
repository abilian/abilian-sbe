from flask import g


def page_exists(title: str) -> bool:
    from abilian.sbe.apps.wiki.models import WikiPage

    title = title.strip()
    return (
        WikiPage.query.filter(
            WikiPage.community_id == g.community.id, WikiPage.title == title
        ).count()
        > 0
    )
