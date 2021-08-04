from __future__ import annotations

from abilian.sbe.app import Application


def register_plugin(app: Application):
    from .actions import register_actions
    from .views import wiki

    wiki.record_once(register_actions)
    app.register_blueprint(wiki)
