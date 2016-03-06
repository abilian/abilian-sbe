def register_plugin(app):
    from .views import wiki
    from .actions import register_actions

    wiki.record_once(register_actions)
    app.register_blueprint(wiki)
