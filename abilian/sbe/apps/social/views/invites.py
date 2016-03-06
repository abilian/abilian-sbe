"""
Not used!
"""

from flask import flash, g, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_mail import Message as Email
from sqlalchemy.schema import Column
from sqlalchemy.types import Text

from abilian.core.extensions import db, mail

from .social import social


class Invite(db.Model):
    """Tracks a pending invitation to join the community."""

    __tablename__ = 'invitation'

    email = Column(Text, nullable=False)

    query = db.session.query_property()


@social.route("/invite")
def invite():
    return render_template("social/invite.html")


@social.route("/invite", methods=['POST'])
def invite_post():
    action = request.form.get("action", "cancel")
    if action == 'cancel':
        flash(_(u"Action aborted"), "info")
        return redirect(url_for(".home"))

    emails = request.form.get("emails").split("\n")
    emails = [email.strip() for email in emails]

    # FIXME: what do we do with this ?
    message = request.form.get("message", "")  # noqa

    with mail.connect() as conn:
        for email in emails:
            # FIXME: what do we do with this ?
            invite = Invite(sender=g.user, email=email)  # noqa

            #subject = _(u"%s would like to invite you to the %s community") % (g.user.name, "Yaka")
            subject = "%s would like to invite you to the %s community" % (
                g.user.name, "Yaka")
            msg = Email(subject, recipients=[email], sender=g.user.email)
            params = dict(org_name="Yaka")
            msg.body = render_template('social/mail/invite.txt', **params)
            conn.send(msg)

    flash(_(u"Invitation sent"), "info")
    return redirect(url_for(".home"))
