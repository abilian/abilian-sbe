# Copyright (c) 2026, Abilian SAS

"""The e-mail that tells someone they are in a community now: who put them there, the
word that came with it, and the way in: for one who never signed in, the link to
choose a password; for the others, the community's page."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app

from abilian.i18n import _
from abilian.services.auth.views import password_link, send_mail
from abilian.web.util import url_for

if TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.sbe.apps.communities.models import Community


def send_invitation(user: User, community: Community, inviter: User, note: str) -> None:
    """Tell `user` that `inviter` put them in `community`, with `note` if any."""
    first_time = not user.last_active
    link = password_link(user) if first_time else url_for(community, _external=True)
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
        user=user,
        community=community,
        inviter=inviter,
        note=note,
        link=link,
        first_time=first_time,
    )
