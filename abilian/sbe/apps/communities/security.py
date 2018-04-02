"""Decorators and helpers to check access to communities."""

from __future__ import absolute_import, print_function, unicode_literals

from functools import wraps

from abilian.services import get_service
from abilian.services.security import MANAGE
from flask import g
from flask_login import current_user
from werkzeug.exceptions import Forbidden


def require_admin(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        security = get_service('security')
        is_admin = security.has_role(current_user, 'admin')
        if not is_admin:
            raise Forbidden()
        return func(*args, **kwargs)

    return decorated_view


def require_manage(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        community = getattr(g, 'community')
        if community and community.has_permission(current_user, MANAGE):
            return func(*args, **kwargs)
        security = get_service('security')
        is_admin = security.has_role(current_user, 'admin')
        if not is_admin:
            raise Forbidden()
        return func(*args, **kwargs)

    return decorated_view


def require_access(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        check_access()
        return func(*args, **kwargs)

    return decorated_view


def check_access(community=None, user=None):
    if not has_access(community, user):
        raise Forbidden()


def has_access(community=None, user=None):
    if not user:
        user = current_user
    if user.is_anonymous:
        return False

    security = get_service('security')
    is_admin = security.has_role(user, 'admin')
    if is_admin:
        return True

    if not community:
        community = getattr(g, 'community', None)

    if community is not None:
        return community.get_role(user) is not None

    return False


def is_manager(context=None, user=None):
    security = get_service('security')

    if not user:
        user = current_user
    if user.is_anonymous:
        return False

    if context:
        community = context.get('object').community
    else:
        community = g.community

    if community.has_permission(user, MANAGE) or\
            user == community.creator:
        return True

    if security.has_role(user, 'admin'):
        return True

    return False
