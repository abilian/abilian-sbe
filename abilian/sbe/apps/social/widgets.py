# coding=utf-8
""""""
from __future__ import absolute_import, print_function, unicode_literals

from flask import Markup, render_template


class UserPhotoInputWidget(object):
    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        user_id = None

        if 'widget_options' in kwargs:
            options = kwargs.pop('widget_options')
            user_id = options.get('user_id')

        return Markup(
            render_template(
                'social/widget_user_photo.html',
                field=field,
                attrs=kwargs,
                user_id=user_id,
            ),
        )
