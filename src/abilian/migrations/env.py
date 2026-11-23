from __future__ import annotations

from logging.config import fileConfig

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from flask import current_app

config.set_main_option(
    "sqlalchemy.url", current_app.config.get("SQLALCHEMY_DATABASE_URI")
)
target_metadata = current_app.extensions["migrate"].db.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # The application's own engine: the database it runs on, an in-memory
    # SQLite included, and not a second engine made from the URL.
    connectable = current_app.extensions["migrate"].db.engine

    with connectable.connect() as connection:
        on_sqlite = connection.dialect.name == "sqlite"
        if on_sqlite:
            # Batch mode changes a table on SQLite by copying it and dropping
            # the original, which SQLite refuses while other rows reference it
            # and foreign keys are enforced. The pragma is ignored inside a
            # transaction: it is set, and committed, before the migrations.
            _set_sqlite_foreign_keys(connection, enforced=False)
        try:
            context.configure(connection=connection, target_metadata=target_metadata)

            with context.begin_transaction():
                context.run_migrations()
        finally:
            if on_sqlite:
                _set_sqlite_foreign_keys(connection, enforced=True)


def _set_sqlite_foreign_keys(connection, *, enforced: bool) -> None:
    state = "ON" if enforced else "OFF"
    connection.exec_driver_sql(f"PRAGMA foreign_keys={state}")
    connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
