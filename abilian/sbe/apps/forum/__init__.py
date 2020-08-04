"""Forum module."""


from abilian.sbe.app import Application


def register_plugin(app: Application) -> None:
    app.config.setdefault("SBE_FORUM_REPLY_BY_MAIL", False)
    app.config.setdefault("INCOMING_MAIL_USE_MAILDIR", False)

    from . import tasks
    from .actions import register_actions
    from .cli import check_email, inject_email
    from .models import ThreadIndexAdapter
    from .views import forum

    forum.record_once(register_actions)
    app.register_blueprint(forum)
    app.services["indexing"].adapters_cls.insert(0, ThreadIndexAdapter)
    tasks.init_app(app)

    app.cli.add_command(check_email)
    app.cli.add_command(inject_email)
