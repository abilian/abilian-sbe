from abilian.sbe.app import Application


def register_plugin(app: Application) -> None:
    from .views import wall

    app.register_blueprint(wall)
