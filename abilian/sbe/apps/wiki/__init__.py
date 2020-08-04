from abilian.sbe.app import Application


def register_plugin(app: Application) -> None:
    from .actions import register_actions
    from .views import wiki

    wiki.record_once(register_actions)
    app.register_blueprint(wiki)
