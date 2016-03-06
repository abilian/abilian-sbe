"""
Decorators and helpers to check access to communities.
"""

from functools import wraps

from flask import current_app, g
from flask_login import current_user
from werkzeug.exceptions import Forbidden


def require_admin(func):

    @wraps(func)
    def decorated_view(*args, **kwargs):
        security = current_app.services['security']
        is_admin = security.has_role(current_user, 'admin')
        if not is_admin:
            raise Forbidden()
        return func(*args, **kwargs)

    return decorated_view


def require_manage(func):

    @wraps(func)
    def decorated_view(*args, **kwargs):
        community = getattr(g, 'community')
        if community and community.has_permission(current_user, 'manage'):
            return func(*args, **kwargs)
        security = current_app.services['security']
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
    if user.is_anonymous():
        return False

    security = current_app.services['security']
    is_admin = security.has_role(user, 'admin')
    if is_admin:
        return True

    if not community:
        community = getattr(g, 'community', None)

    if community is not None:
        return community.get_role(user) is not None

    return False
