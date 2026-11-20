from __future__ import annotations

import operator
import os
from importlib.metadata import distributions
from typing import TYPE_CHECKING, cast

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import command

if TYPE_CHECKING:
    from pathlib import Path


@command("extensions")
@with_appcontext
def extensions_command():
    """Lists all the extensions currently present in the Flask app."""
    click.echo("Installed Flask extensions:")
    for extension in sorted(current_app.extensions.keys()):
        click.echo(f"- {extension}")


@command(short_help="Show config")
@with_appcontext
def config() -> None:
    config_ = dict(sorted(current_app.config.items()))
    print("CONFIG:\n")
    for k, v in config_.items():
        try:
            print(f"{k}: {v}")
        except Exception as e:
            print(f"{k}: {e}")

    print("\nENV:\n")

    env_ = dict(sorted(os.environ.items()))
    for k, v in env_.items():
        print(f"{k}: {v}")


# @command(name="debug", short_help="Show debug information")
# @with_appcontext
# def _debug() -> None:
#     rich.print(blue("List of registered pages"))
#     print()
#
#     pages = get_pages()
#     for key, _value in sorted(pages.items()):
#         rich.print(f"{key}")
#
#     print()
#
#     rich.print(blue("List of registered components"))
#     print()
#     components = get_components()
#     for key, _value in sorted(components.items()):
#         rich.print(f"{key}")
#
#     print()
#
#     rich.print(blue("List of template globals"))
#     print()
#     for key, _value in sorted(current_app.jinja_env.globals.items()):
#         rich.print(f"{key}")
#
#     print()


# @command("health-check", short_help="Health check")
# @with_appcontext
# def check() -> None:
#     db.session.execute(text("select 1"))
#     print("db test OK")
#     return


# @command("test-email", short_help="Send test email")
# @click.option("--from")
# @click.option("--to")
# @with_appcontext
# def send_test_email(from: str, to: str) -> None:
#     for k in sorted(current_app.config.keys()):
#         if not k.startswith("MAIL"):
#             continue
#         print(f"{k}: {current_app.config[k]}")
#
#     message = EmailMessage(
#         subject="Flask-Mailing module",
#         to=[""],
#         body="This is the basic email body",
#     )
#     message.send()


# @command(short_help="Load DB from a dump")
# @with_appcontext
# def load_db() -> None:
#     try:
#         res = db.session.execute(text("select count(*) from aut_user"))
#         first_row = res.first()
#         assert first_row is not None
#         if first_row[0] > 0:
#             print("Database is not empty")
#             return
#     except sqlalchemy.exc.ProgrammingError:
#         pass
#
#     print(green("Loading database..."))
#
#     url = yarl.URL(current_app.config["SQLALCHEMY_DATABASE_URI"])
#     host = url.host
#     port = url.port
#     db_name = url.path[1:]
#     user = url.user
#     password = url.password
#
#     cmd = ["pg_restore", "-c", "-h", host, "-d", db_name]
#     if port:
#         cmd += ["-p", str(port)]
#     if user:
#         cmd += ["-U", user]
#     cmd += ["db/db.dump"]
#
#     env = os.environ.copy()
#     if password:
#         env["PGPASSWORD"] = password
#
#     print(shlex.join(cmd))
#     print(list(Path("db").glob("*")))
#     subprocess.run(cmd, env=env, check=True)


@command(short_help="List installed packages")
def packages() -> None:
    sizes = []
    for distribution in distributions():
        size = 0
        files = distribution.files or []
        for file in files:
            path = cast("Path", file.locate())
            if not path.exists():
                continue
            size += path.stat().st_size

        sizes += [(size, distribution)]

    sizes.sort(key=operator.itemgetter(0), reverse=True)

    packages_info = [("Size", "Name", "Version")]
    for size, distribution in sizes:
        name = distribution.metadata["Name"]
        version = distribution.metadata["Version"]
        size_str = f"{size / 1024 / 1024:.2f} MB"
        packages_info += [(size_str, name, version)]
        print(f"{size_str} {name} {version}")
