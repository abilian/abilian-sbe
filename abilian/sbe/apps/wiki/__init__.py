# coding=utf-8


from abilian.sbe.app import Application


def register_plugin(app: Application) -> None:
    from .views import wiki
    from .actions import register_actions

    wiki.record_once(register_actions)
    app.register_blueprint(wiki)
