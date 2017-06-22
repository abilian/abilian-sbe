# coding=utf-8
"""
"""
from __future__ import absolute_import, print_function

import csv
import json

from flask import current_app, flash, g, redirect, render_template, request, \
    url_for
from validate_email import validate_email
from werkzeug.utils import secure_filename

from abilian.core.extensions import db
from abilian.core.models.subjects import User
from abilian.core.signals import activity
from abilian.i18n import _
from abilian.services.auth.views import send_reset_password_instructions
from abilian.web import csrf
from abilian.web.action import Endpoint
from abilian.web.nav import BreadcrumbItem

from .views import route, tab


def wizard_extract_data(emails, is_csv=False):
    """Filter data and extract existing accounts, existing members and new emails"""
    if is_csv:
        csv_data = emails
        existing_account_csv_roles = {
            user["email"]: user["role"]
            for user in csv_data
        }
        emails = [user["email"] for user in emails]

    emails = [email.strip() for email in emails]

    already_member_emails = [
        member.email for member in g.community.members if member.email in emails
    ]
    not_member_emails = set(emails) - set(already_member_emails)

    existing_members_objects = filter(
        lambda user: user.email in already_member_emails, g.community.members)

    existing_accounts_objects = User.query.filter(
        User.email.in_(not_member_emails)).all()
    existing_account_emails = [user.email for user in existing_accounts_objects]

    emails_without_account = set(not_member_emails) - set(
        existing_account_emails)

    accounts_list = []
    for user in existing_accounts_objects:
        account = {}
        account["email"] = user.email
        account["first_name"] = user.first_name
        account["last_name"] = user.last_name
        account["role"] = existing_account_csv_roles[
            user.email] if is_csv else "member"
        account["status"] = "existing"
        accounts_list.append(account)

    if is_csv:
        emails_without_account = [
            csv_account for csv_account in csv_data
            if csv_account["email"] in emails_without_account
        ]
        existing_accounts_objects = {
            "account_objects": existing_accounts_objects,
            "csv_roles": existing_account_csv_roles
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
        for email in emails_without_account:
            account = {}
            account["email"] = email
            account["first_name"] = ""
            account["last_name"] = ""
            account["role"] = "member"
            account["status"] = "new"
            accounts_list.append(account)

    return existing_accounts_objects, existing_members_objects, accounts_list


def wizard_read_csv(csv_file):
    """read new members data from csv file"""
    file_extension = secure_filename(csv_file.filename).split(".")[-1]

    if file_extension != "csv":
        return []

    contents = csv.reader(csv_file, delimiter=";")
    new_accounts = []

    for row in contents:
        account = {}
        if len(row) != 4:
            continue

        email = row[0].strip()
        first_name = row[1].strip()
        last_name = row[2].strip()
        role = row[3].strip()

        if not validate_email(email):
            continue
        if role.lower() not in ["manager", "member"]:
            continue

        account["email"] = email
        account["first_name"] = first_name
        account["last_name"] = last_name
        account["role"] = role
        new_accounts.append(account)

    return new_accounts


@route("/<string:community_id>/members/wizard/step1")
@tab('members')
def wizard_data_insertion():
    """
    Insertion of new members data into the community via emails or csv file
    """
    g.breadcrumb.append(BreadcrumbItem(
        label=_(u'Members'),
        url=Endpoint('communities.members', community_id=g.community.slug))
    )

    return render_template(
        "community/wizard_add_emails.html", csrf_token=csrf.field())


@route("/<string:community_id>/members/wizard/step2", methods=['GET', 'POST'])
@csrf.protect
@tab('members')
def wizard_check_data():
    """
    Filter and detect existing members, existing accounts and new emails
    """
    if request.method == "GET":
        return redirect(url_for(".members", community_id=g.community.slug))

    g.breadcrumb.append(BreadcrumbItem(
        label=_(u'Members'),
        url=Endpoint('communities.members', community_id=g.community.slug))
    )

    is_csv = False
    if request.form.get("wizard-emails"):
        wizard_emails = request.form.get("wizard-emails").split(",")
        existing_accounts_object, existing_members_objects, final_email_list = wizard_extract_data(
            wizard_emails)
        final_email_list_json = json.dumps(final_email_list)
    else:
        is_csv = True
        accounts_data = wizard_read_csv(request.files['csv_file'])
        if not accounts_data:
            flash(_(u"To add new members, please follow the CSV file model."), 'warning')
            return redirect(
                url_for(
                    ".wizard_data_insertion", community_id=g.community.slug))

        existing_accounts, existing_members_objects, final_email_list = wizard_extract_data(
            accounts_data, is_csv=True)
        existing_accounts_object = existing_accounts["account_objects"]
        existing_accounts_csv_roles = existing_accounts["csv_roles"]
        final_email_list_json = json.dumps(final_email_list)

    if not final_email_list:
        flash(_(u"No new members were found"), 'warning')
        return redirect(
            url_for(".wizard_data_insertion", community_id=g.community.slug))

    return render_template(
        "community/wizard_check_members.html",
        existing_accounts_object=existing_accounts_object,
        csv_roles=existing_accounts_csv_roles if is_csv else False,
        wizard_emails=final_email_list_json,
        existing_members_objects=existing_members_objects,
        csrf_token=csrf.field())


@route("/<string:community_id>/members/wizard/step3", methods=['GET', 'POST'])
@csrf.protect
@tab('members')
def wizard_new_accounts():
    """
    Complete new emails information
    """
    if request.method == "GET":
        return redirect(url_for(".members", community_id=g.community.slug))

    g.breadcrumb.append(BreadcrumbItem(
        label=_(u'Members'),
        url=Endpoint('communities.members', community_id=g.community.slug))
    )

    wizard_emails = request.form.get("wizard-emails")
    wizard_accounts = json.loads(wizard_emails)

    wizard_existing_account = {}
    new_accounts = []

    for user in wizard_accounts:
        if user["status"] == "existing":
            wizard_existing_account[user["email"]] = user["role"]

        elif user["status"] == "new":
            new_accounts.append(user)

    existing_account = json.dumps(wizard_existing_account)

    return render_template(
        "community/wizard_new_accounts.html",
        existing_account=existing_account,
        new_accounts=new_accounts,
        csrf_token=csrf.field())


@route("/<string:community_id>/members/wizard/complete", methods=['POST'])
@csrf.protect
def wizard_saving():
    """
    Automatically add existing accounts to the current community.
    Create accounts for new emails, add them to the community and send them a password reset email
    """
    community = g.community._model
    existing_accounts = request.form.get("existing_account")
    existing_accounts = json.loads(existing_accounts)
    new_accounts = request.form.get("new_accounts")
    new_accounts = json.loads(new_accounts)

    if not (existing_accounts or new_accounts):
        flash(_(u"No new members were found"), 'warning')
        return redirect(url_for(".members", community_id=g.community.slug))

    if existing_accounts:
        for email, role in existing_accounts.iteritems():
            user = User.query.filter(User.email == email).first()
            community.set_membership(user, role)

            app = current_app._get_current_object()
            activity.send(app, actor=user, verb="join", object=community)

            db.session.commit()

    if new_accounts:
        for account in new_accounts:
            email = account["email"]
            first_name = account["first_name"]
            last_name = account["last_name"]
            role = account["role"]

            user = User(
                email=email,
                last_name=last_name,
                first_name=first_name,
                can_login=True)
            db.session.add(user)

            community.set_membership(user, role)
            app = current_app._get_current_object()
            activity.send(app, actor=user, verb="join", object=community)
            db.session.commit()

            send_reset_password_instructions(user)

    flash(_(u"Members added Successfully"), 'success')
    return redirect(url_for(".members", community_id=community.slug))
