# Copyright (c) 2012-2024, Abilian SAS

"""Seed the throwaway e2e instance with a community.

Run by serve.sh via `flask script`, so it executes inside the app context.

Without a community there is nothing to point the browser at for the documents
module -- the folder listing and the modal stack -- which is
where the front end is most intricate and least covered.
"""

from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw

from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User
from abilian.sbe.apps.communities.models import MANAGER, Community
from abilian.sbe.apps.forum.models import Thread

COMMUNITY_NAME = "E2E Community"
EXISTING_FOLDER = "Existing Folder"
ADMIN_EMAIL = os.environ.get("E2E_EMAIL", "admin@example.com")

existing = Community.query.filter(Community.name == COMMUNITY_NAME).first()
if existing is None:
    community = Community(name=COMMUNITY_NAME)
    db.session.add(community)

    admin = User.query.filter(User.email == ADMIN_EMAIL).one()
    # MANAGER, not the global ADMIN role: set_membership only accepts
    # community roles (READER, WRITER, MANAGER, MEMBER).
    community.set_membership(admin, MANAGER)

    db.session.commit()

    # A document, so the folder listing renders its table: an empty folder
    # takes a different, table-less path and would not exercise folder.js.
    # An image, because its thumbnail is the image itself, resized: any other
    # type goes through the external converters, and its thumbnail would
    # depend on which of them the machine has, which the screenshots cannot.
    picture = Image.new("RGB", (160, 120), "#2563eb")
    ImageDraw.Draw(picture).rectangle((0, 70, 160, 120), fill="#f59e0b")
    png = io.BytesIO()
    picture.save(png, "PNG")
    doc = community.folder.create_document(title="E2E Sample.png")
    doc.set_content(png.getvalue(), "image/png")
    # The listing renders url_for(..., user_id=obj.owner.id) with no guard, so a
    # document without an owner 500s the whole folder. Outside a request there is
    # no current_user to default from, so set it explicitly.
    doc.owner = admin
    doc.creator = admin
    db.session.commit()

    # A subfolder to collide with, so the title-uniqueness check in
    # folder_edit.js has something to reject.
    subfolder = community.folder.create_subfolder(EXISTING_FOLDER)
    subfolder.owner = admin
    subfolder.creator = admin
    db.session.commit()

    # A thread with one post, so the forum renders its stats strip and the
    # per-thread actions ("Close thread", "Attachments") -- none of which appear
    # on an empty forum.
    thread = Thread(title="Welcome to the new members", community=community)
    thread.creator = thread.owner = admin
    post = thread.create_post(
        body_html="<p>A quick message to welcome the new members.</p>"
    )
    post.creator = post.owner = admin
    db.session.add(thread)
    db.session.add(Group(name="E2E Group"))
    db.session.commit()

    # Accounts that are not members of anything: one for each test that adds
    # someone, since adding them is not undone.
    for first_name, last_name in (
        ("Eva", "Existing"),
        ("Rita", "Removed"),
        ("Paula", "Picker"),
        ("Rolf", "Roleholder"),
        ("Gus", "Grouped"),
        ("Greta", "Groupadmin"),
    ):
        db.session.add(
            User(
                email=f"{first_name}.{last_name}@example.com".lower(),
                first_name=first_name,
                last_name=last_name,
                can_login=True,
            )
        )
    db.session.commit()

    print(
        f"seeded community {community.slug!r} with 1 document and 1 thread "
        f"for {ADMIN_EMAIL}"
    )
else:
    print(f"community {existing.slug!r} already present")


# --- Dashboard history -------------------------------------------------------
#
# The admin dashboard's two charts are the only place the front end draws
# anything from a time series. With a single account created five minutes ago
# they render one point each, which is not enough for the widget test to tell a
# working chart from a broken one -- so give it some history to draw.

SEEDED_USERS = 12
SEEDED_YEARS = 3


def seed_dashboard_history() -> None:
    """Twelve accounts, spread over three years, with logins that taper off.

    Everything here is derived from the loop index rather than drawn at random,
    so two runs seed the same database and screenshots stay comparable.
    """
    from datetime import UTC, datetime, timedelta

    from abilian.services.auth.models import LoginSession

    if LoginSession.query.count() > 0:
        print("dashboard history already present")
        return

    now = datetime.now(UTC).replace(tzinfo=None)
    span = timedelta(days=SEEDED_YEARS * 365)

    for n in range(SEEDED_USERS):
        # Signups cluster early and then trickle, the usual growth curve.
        joined = now - span + span * (n / SEEDED_USERS) ** 0.6
        user = User(
            email=f"seed-{n}@example.com",
            first_name="Seed",
            last_name=f"User {n}",
            can_login=False,
        )
        db.session.add(user)
        db.session.flush()
        user.created_at = joined

        # Each account is used for a while and then goes quiet, so the active
        # line falls away from the registered one.
        day = joined
        last_day = min(joined + timedelta(days=30 + (n * 397) % 900), now)
        while day < last_day:
            db.session.add(LoginSession(user=user, started_at=day, last_active_at=day))
            day += timedelta(days=1 + (day.toordinal() * 7 + n) % 12)

    db.session.commit()
    print(
        f"seeded {SEEDED_USERS} users and {LoginSession.query.count()} login sessions"
    )


seed_dashboard_history()
