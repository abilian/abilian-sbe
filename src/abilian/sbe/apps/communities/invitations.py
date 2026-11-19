# Copyright (c) 2026, Abilian SAS

"""The e-mail that tells someone they are in a community now: who put them there, the
word that came with it, and the way in: for one who never signed in, the link to
choose a password; for the others, the community's page. And the one that tells a
community's managers that someone asks to join it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app

from abilian.i18n import _, force_locale, get_default_locale
from abilian.services.auth.views import password_link, send_mail
from abilian.web.util import url_for

from .models import managers_of

if TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.sbe.apps.communities.models import Community, MembershipRequest


def send_invitation(user: User, community: Community, inviter: User, note: str) -> None:
    """Tell `user` that `inviter` put them in `community`, with `note` if any."""
    first_time = not user.last_active
    link = password_link(user) if first_time else url_for(community, _external=True)
    # In the language of whoever is invited, the site's until they choose one.
    locale = user.locale or get_default_locale()
    with force_locale(locale):
        subject = _(
            "%(inviter)s invites you to %(community)s on %(site)s",
            inviter=inviter.name,
            community=community.name,
            site=current_app.config.get("SITE_NAME"),
        )
    send_mail(
        subject,
        user.email,
        "community_invitation",
        locale=locale,
        user=user,
        community=community,
        inviter=inviter,
        note=note,
        link=link,
        first_time=first_time,
    )


def send_join_request(asking: MembershipRequest) -> None:
    """Tell the managers of the community `asking` is for, each in their language,
    who asks to join it, and where to answer."""
    community, user = asking.community, asking.user
    link = url_for("communities.members", community_id=community.slug, _external=True)
    for manager in managers_of([community]).get(community.id, []):
        locale = manager.locale or get_default_locale()
        with force_locale(locale):
            subject = _(
                "%(name)s asks to join %(community)s",
                name=user.name,
                community=community.name,
            )
        send_mail(
            subject,
            manager.email,
            "community_join_request",
            locale=locale,
            manager=manager,
            user=user,
            community=community,
            link=link,
        )
