"""Register extensions as a plugin.

NOTE: panels are currently loaded and registered manually. This may change
in the future.
"""


from abilian.sbe.app import Application


def register_plugin(app: Application) -> None:
    from .main import blueprint

    app.register_blueprint(blueprint)
