# coding=utf-8
from flask import url_for as url_for_orig
from flask import g
from flask_babel import lazy_gettext as _l
from flask_login import current_user

from abilian.web.action import Action, Endpoint, actions
from abilian.web.nav import NavItem

__all__ = ['register_actions']


def url_for(endpoint, **kw):
    return url_for_orig(endpoint, community_id=g.community.slug, **kw)


class CommunityEndpoint(Endpoint):

    def get_kwargs(self):
        kwargs = super(CommunityEndpoint, self).get_kwargs()
        kwargs['community_id'] = g.community.slug
        return kwargs


class CommunityTabAction(Action):

    Endpoint = CommunityEndpoint

    def url(self, context=None):
        if self._url:
            return Action.url(self)

        endpoint = self.endpoint
        if endpoint:
            return endpoint
        else:
            return url_for("%s.index" % self.name)

    def is_current(self):
        return g.current_tab == self.name


_actions = (
    # Navigation
    NavItem('section',
            'communities',
            title=_l(u'Communities'),
            url=lambda context: url_for_orig('communities.index'),
            condition=lambda ctx: current_user.is_authenticated()),
    # Tabs
    CommunityTabAction('communities:tabs', 'wall', _l(u'Activities')),
    CommunityTabAction('communities:tabs',
                       'documents',
                       _l(u'Documents'),
                       condition=lambda ctx: g.community.has_documents),
    CommunityTabAction('communities:tabs',
                       'wiki',
                       _l(u'Wiki'),
                       condition=lambda ctx: g.community.has_wiki),
    CommunityTabAction('communities:tabs',
                       'forum',
                       _l(u'Conversations'),
                       condition=lambda ctx: g.community.has_forum),
    CommunityTabAction('communities:tabs',
                       'members',
                       _l(u'Members'),
                       endpoint="communities.members"),
    CommunityTabAction('communities:tabs',
                       'settings',
                       _l(u'Settings'),
                       icon='cog',
                       condition=lambda ctx: current_user.has_role("admin"),
                       endpoint="communities.settings"))


def register_actions(state):
    if not actions.installed(state.app):
        return
    with state.app.app_context():
        actions.register(*_actions)
