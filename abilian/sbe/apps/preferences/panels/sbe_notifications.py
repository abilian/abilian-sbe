# coding=utf-8
"""
This panel manages user setting for email reminders related to the SBE
(social netowking) app.
"""
from flask import current_app as app
from flask import flash, redirect, render_template, request, url_for
from werkzeug.exceptions import InternalServerError
from wtforms import BooleanField

from abilian.core.extensions import db
from abilian.i18n import _, _l
from abilian.services.preferences.panel import PreferencePanel
from abilian.web import csrf
from abilian.web.forms import Form, widgets


class SbeNotificationsForm(Form):
    daily = BooleanField(
        label=_(u"Receive by email a daily digest of activities in your communities"),
        widget=widgets.BooleanWidget(on_off_mode=True))


class SbeNotificationsPanel(PreferencePanel):
    id = 'sbe_notifications'
    label = _l(u'Community notifications')

    def is_accessible(self):
        return True

    def get(self):
        # Manual security check, should be done by the framework instead.
        if not self.is_accessible():
            raise InternalServerError()

        preferences = app.services['preferences']
        data = {}
        prefs = preferences.get_preferences()

        for k, v in prefs.items():
            if k.startswith("sbe:notifications:"):
                data[k[18:]] = v

        form = SbeNotificationsForm(formdata=None, prefix=self.id, **data)
        return render_template("preferences/sbe_notifications.html", form=form)

    @csrf.protect
    def post(self):
        # Manual security check, should be done by the framework instead.
        if not self.is_accessible():
            raise InternalServerError()

        if request.form['_action'] == 'cancel':
            return redirect(url_for(".sbe_notifications"))
        form = SbeNotificationsForm(request.form, prefix=self.id)
        if form.validate():
            preferences = app.services['preferences']
            for field_name, field in form._fields.items():
                if field is form.csrf_token:
                    continue
                key = 'sbe:notifications:{}'.format(field_name)
                value = field.data
                preferences.set_preferences(**{key: value})

            db.session.commit()
            flash(_(u"Preferences saved."), "info")
            return redirect(url_for(".sbe_notifications"))
        else:
            return render_template("preferences/sbe_notifications.html",
                                   form=form,
                                   csrf_token=csrf.field())
