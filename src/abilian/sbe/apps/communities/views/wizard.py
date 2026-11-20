# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import csv
import io
import json
import re
import smtplib
from dataclasses import dataclass
from os.path import splitext
from typing import IO, TYPE_CHECKING, Any

import sqlalchemy as sa
from flask import current_app, flash, g, redirect, render_template, request, url_for
from validate_email import validate_email
from werkzeug.exceptions import BadRequest

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated_user
from abilian.core.models.subjects import User
from abilian.core.signals import activity
from abilian.core.util import unwrap
from abilian.i18n import _
from abilian.sbe.apps.communities.decorators import can_manage
from abilian.sbe.apps.communities.invitations import send_invitation
from abilian.web import csrf
from abilian.web.action import Endpoint
from abilian.web.nav import BreadcrumbItem

from .views import route, tab

if TYPE_CHECKING:
    from collections.abc import Sequence

    from werkzeug.datastructures import MultiDict
    from werkzeug.wrappers import Response


#: The roles one is invited with.
INVITED_ROLES = ("member", "manager")

#: The longest word a manager may write to go with an invitation.
NOTE_LENGTH = 1000

#: People paste addresses from anywhere: a spreadsheet column, a mail header.
EMAIL_SEPARATORS = re.compile(r"[\s,;]+")


@dataclass(frozen=True)
class Invitee:
    """An address typed in, its account if it has one, and what inviting does to it:
    nothing for a `member`; adds an `account`; adds, and sends the invitation again
    to, an account `invited` that never signed in; makes a `new` one; ignores an
    `invalid` address. Each one added is told by e-mail."""

    email: str
    status: str
    user: User | None = None

    @property
    def gets_email(self) -> bool:
        return self.status in {"account", "invited", "new"}


def classify_invitees(text: str) -> list[Invitee]:
    """What inviting the addresses in `text` to the current community does to each,
    in the order they came."""
    valid, invalid = wizard_parse_emails(text)
    accounts = {
        user.email.lower(): user
        for user in User.query.filter(
            sa.func.lower(User.email).in_([email.lower() for email in valid])
        )
    }
    members = {user.id for user in g.community.members}
    invitees = [Invitee(email, "invalid") for email in invalid]
    for email in valid:
        user = accounts.get(email.lower())
        if user is None:
            invitees.append(Invitee(email, "new"))
        elif user.id in members:
            invitees.append(Invitee(email, "member", user))
        elif user.can_login and not user.last_active:
            invitees.append(Invitee(email, "invited", user))
        else:
            invitees.append(Invitee(email, "account", user))
    return invitees


@route("/<string:community_id>/members/wizard/preview", methods=["POST"])
@csrf.protect
@can_manage
def wizard_preview() -> str:
    """What inviting the addresses typed so far would do to each: a piece of the
    first page, which `vite/src/preview.js` puts under the field as one types. Posted,
    the first page's form as it is: a long list makes too long an address."""
    invitees = classify_invitees(request.form.get("wizard-emails", ""))
    return render_template("community/_invitees.html", invitees=invitees)


def _account(email: str) -> User:
    """The account an address names, whatever its case."""
    user = User.query.filter(sa.func.lower(User.email) == email.lower()).first()
    if user is None:
        msg = f"No account for {email!r}"
        raise BadRequest(msg)
    return user


def _new_account(account: dict[str, str]) -> User:
    """An account for an address that has none, named if a spreadsheet named it;
    refused if one came meanwhile."""
    email = account["email"]
    if User.query.filter(sa.func.lower(User.email) == email.lower()).count():
        msg = f"{email!r} has an account already"
        raise BadRequest(msg)
    user = User(
        email=email,
        first_name=account.get("first_name") or None,
        last_name=account.get("last_name") or None,
        can_login=True,
    )
    db.session.add(user)
    return user


def invitation_note(form: MultiDict[str, str]) -> str:
    """The word a manager wrote to go with the invitation; refused if too long."""
    note = form.get("note", "").strip()
    if len(note) > NOTE_LENGTH:
        msg = f"An invitation's note is at most {NOTE_LENGTH} characters"
        raise BadRequest(msg)
    return note


def wizard_parse_emails(text: str) -> tuple[list[str], list[str]]:
    """Split pasted text into its valid and invalid addresses, without repeats: an
    address is the same whatever its case, as the accounts' index has it."""
    first_seen: dict[str, str] = {}
    for address in filter(None, EMAIL_SEPARATORS.split(text)):
        first_seen.setdefault(address.lower(), address)
    addresses = list(first_seen.values())
    valid = [address for address in addresses if validate_email(address)]
    invalid = [address for address in addresses if address not in valid]
    return valid, invalid


def wizard_extract_data(
    emails: Sequence[str] = (), csv_data: Sequence[dict[str, str]] = ()
) -> tuple[dict[str, Any] | list[User], list[User], list[dict[str, str | None]]]:
    """Filter data and extract existing accounts, existing members and new
    emails."""
    if csv_data:
        existing_account_csv_roles = {
            user["email"].lower(): user["role"] for user in csv_data
        }
        emails = [user["email"] for user in csv_data]
        is_csv = True
    else:
        is_csv = False

    # An address is the same whatever its case, as the accounts' index has it.
    emails = [email.strip() for email in emails]
    members = {member.email.lower(): member for member in g.community.members}
    existing_members_objects = [
        members[email.lower()] for email in emails if email.lower() in members
    ]
    not_member_emails = [email for email in emails if email.lower() not in members]

    accounts = {
        user.email.lower(): user
        for user in User.query.filter(
            sa.func.lower(User.email).in_(
                [email.lower() for email in not_member_emails]
            )
        )
    }
    existing_accounts_objects = list(accounts.values())
    emails_without_account = {
        email.lower() for email in not_member_emails if email.lower() not in accounts
    }

    accounts_list = []
    for user in existing_accounts_objects:
        account = {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": existing_account_csv_roles[user.email.lower()]
            if is_csv
            else "member",
            "status": "existing",
        }
        accounts_list.append(account)

    if is_csv:
        emails_without_account = [
            csv_account
            for csv_account in csv_data
            if csv_account["email"].lower() in emails_without_account
        ]
        existing_accounts_objects = {
            "account_objects": existing_accounts_objects,
            "csv_roles": existing_account_csv_roles,
        }

        for csv_account in emails_without_account:
            account = {}
            account["email"] = csv_account["email"]
            account["first_name"] = csv_account["first_name"]
            account["last_name"] = csv_account["last_name"]
            account["role"] = csv_account["role"]
            account["status"] = "new"
            accounts_list.append(account)

    else:
        for email in dict.fromkeys(
            email for email in not_member_emails if email.lower() not in accounts
        ):
            account = {}
            account["email"] = email
            account["first_name"] = ""
            account["last_name"] = ""
            account["role"] = "member"
            account["status"] = "new"
            accounts_list.append(account)

    return existing_accounts_objects, existing_members_objects, accounts_list


def wizard_read_csv(csv_file: IO[str]) -> list[dict[str, str]]:
    """Read new members data from CSV file."""

    if hasattr(csv_file, "filename"):
        filename = csv_file.filename
    else:
        filename = csv_file.name
    file_extension = splitext(filename)[-1]
    if file_extension != ".csv":
        return []

    raw_data = csv_file.read()
    if isinstance(raw_data, bytes):
        data = raw_data.decode("utf8")  # FIXME
    else:
        data = raw_data

    contents = csv.reader(io.StringIO(data), delimiter=";")

    new_accounts = []
    seen = set()

    for row in contents:
        account = {}
        if len(row) != 4:
            continue

        email = row[0].strip()
        first_name = row[1].strip()
        last_name = row[2].strip()
        role = row[3].strip()

        role = role.lower()
        if not validate_email(email) or email.lower() in seen:
            continue
        if role not in INVITED_ROLES:
            continue
        seen.add(email.lower())

        account["email"] = email
        account["first_name"] = first_name
        account["last_name"] = last_name
        account["role"] = role
        new_accounts.append(account)

    return new_accounts


@route("/<string:community_id>/members/wizard/step1")
@can_manage
@tab("members")
def wizard_data_insertion():
    """Insert new members data into the community via emails or CSV file."""
    g.breadcrumb.append(
        BreadcrumbItem(
            label=_("Members"),
            url=Endpoint("communities.members", community_id=g.community.slug),
        )
    )

    return render_template("community/wizard_add_emails.html")


@route("/<string:community_id>/members/wizard/step2", methods=["GET", "POST"])
@csrf.protect
@can_manage
@tab("members")
def wizard_check_data() -> Response | str:
    """Filter and detect existing members, existing accounts and new emails."""
    if request.method == "GET":
        return redirect(url_for(".members", community_id=g.community.slug))

    g.breadcrumb.append(
        BreadcrumbItem(
            label=_("Members"),
            url=Endpoint("communities.members", community_id=g.community.slug),
        )
    )

    if request.form.get("wizard-emails"):
        wizard_emails, invalid_emails = wizard_parse_emails(
            request.form["wizard-emails"]
        )
        if invalid_emails:
            flash(
                _(
                    "These addresses are not valid and were left out: {addresses}"
                ).format(addresses=", ".join(invalid_emails)),
                "warning",
            )
        _accounts, _members, final_email_list = wizard_extract_data(wizard_emails)
        if not final_email_list:
            flash(_("No new members were found"), "warning")
            return redirect(
                url_for(".wizard_data_insertion", community_id=g.community.slug)
            )
        # The first page said what happens to each address as it was typed, and
        # chose one role for all: nothing left to ask.
        role = request.form.get("role")
        return invite(
            [{**account, "role": role} for account in final_email_list],
            invitation_note(request.form),
        )

    csv_file = request.files.get("csv_file")
    if not (csv_file and csv_file.filename):
        flash(_("No new members were found"), "warning")
        return redirect(
            url_for(".wizard_data_insertion", community_id=g.community.slug)
        )

    accounts_data = wizard_read_csv(csv_file)
    if not accounts_data:
        flash(_("To add new members, please follow the CSV file model."), "warning")
        return redirect(
            url_for(".wizard_data_insertion", community_id=g.community.slug)
        )

    (
        existing_accounts,
        existing_members_objects,
        final_email_list,
    ) = wizard_extract_data(csv_data=accounts_data)
    existing_accounts_object = existing_accounts["account_objects"]
    existing_accounts_csv_roles = existing_accounts["csv_roles"]
    final_email_list_json = json.dumps(final_email_list)

    if not final_email_list:
        flash(_("No new members were found"), "warning")
        return redirect(
            url_for(".wizard_data_insertion", community_id=g.community.slug)
        )

    ctx = {
        "existing_accounts_object": existing_accounts_object,
        "new_accounts": [a for a in final_email_list if a["status"] == "new"],
        "csv_roles": existing_accounts_csv_roles,
        "wizard_emails": final_email_list_json,
        "existing_members_objects": existing_members_objects,
        "note": invitation_note(request.form),
    }
    return render_template("community/wizard_check_members.html", **ctx)


@route("/<string:community_id>/members/wizard/complete", methods=["POST"])
@csrf.protect
@can_manage
def wizard_saving() -> Response:
    """The list the second page checked, as its script left it, invited."""
    return invite(
        json.loads(request.form["wizard-emails"]), invitation_note(request.form)
    )


def invite(entries: list[dict[str, Any]], note: str) -> Response:
    """Add the accounts there are to the community and make the others, each with
    its role; tell each one by e-mail, with the word that came with the invitation:
    one who never signed in gets the link to choose a password, and names
    themselves then if the entry did not. Back to the members."""
    community = g.community._model
    if not entries:
        flash(_("No new members were found"), "warning")
        return redirect(url_for(".members", community_id=community.slug))
    if any(entry["role"] not in INVITED_ROLES for entry in entries):
        msg = "Not a role one is invited with"
        raise BadRequest(msg)

    # All of them in the community, then all of them told: a mail server that fails
    # halfway leaves no one half invited.
    invited = [
        _account(entry["email"])
        if entry["status"] == "existing"
        else _new_account(entry)
        for entry in entries
    ]
    app = unwrap(current_app)
    for user, entry in zip(invited, entries, strict=True):
        community.set_membership(user, entry["role"])
        activity.send(app, actor=user, verb="join", object=community)
    db.session.commit()

    inviter = authenticated_user()
    untold = []
    for user in invited:
        try:
            send_invitation(user, community, inviter, note)
        except (smtplib.SMTPException, OSError):
            untold.append(user.email)
    if untold:
        flash(
            _(
                "Added, but not told by e-mail, which could not be sent: {addresses}"
            ).format(addresses=", ".join(untold)),
            "warning",
        )
    else:
        flash(_("New members added successfully"), "success")
    return redirect(url_for(".members", community_id=community.slug))
