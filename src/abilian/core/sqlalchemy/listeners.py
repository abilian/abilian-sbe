# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import contextlib
import sqlite3
from typing import Any

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.pool
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.event import listens_for
from sqlalchemy.ext.compiler import compiles


@listens_for(sa.pool.Pool, "checkout")
def ping_connection(
    dbapi_connection: Connection, connection_record, connection_proxy
) -> None:
    """Ensure connections are valid.

    From: `http://docs.sqlalchemy.org/en/rel_0_8/core/pooling.html`

    In case db has been restarted pool may return invalid connections.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT 1")
    except Exception as e:
        # optional - dispose the whole pool
        # instead of invalidating one at a time
        # connection_proxy._pool.dispose()

        # raise DisconnectionError - pool will try
        # connecting again up to three times before raising.
        raise sa.exc.DisconnectionError from e
    cursor.close()


#
# Make Sqlite a bit more well-behaved.
#
@sa.event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    if isinstance(dbapi_connection, sqlite3.Connection):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


# Ensure MariaDB preserves id=0 on AUTO_INCREMENT columns (used by root/system User).
@sa.event.listens_for(Engine, "connect")
def _set_mysql_sql_mode(dbapi_connection: Any, connection_record: Any) -> None:
    module_name = type(dbapi_connection).__module__
    if module_name.startswith(("pymysql", "MySQLdb", "mariadb", "mysql")):
        cursor = dbapi_connection.cursor()
        cursor.execute(
            "SET SESSION sql_mode = CONCAT(@@sql_mode, ',NO_AUTO_VALUE_ON_ZERO');"
        )
        cursor.close()


# Preserve microsecond precision on MariaDB/MySQL DateTime columns (matching PostgreSQL/SQLite).
@compiles(sa.types.DateTime, "mysql")
@compiles(sa.types.DateTime, "mariadb")
def _compile_datetime_mysql(element: Any, compiler: Any, **kw: Any) -> str:
    return "DATETIME(6)"


@compiles(sa.types.String, "mysql")
@compiles(sa.types.String, "mariadb")
@compiles(sa.types.Unicode, "mysql")
@compiles(sa.types.Unicode, "mariadb")
def _compile_varchar_mysql(element: Any, compiler: Any, **kw: Any) -> str:
    if not element.length:
        element.length = 255
    return compiler.visit_VARCHAR(element, **kw)


with contextlib.suppress(ImportError):
    import pymysql.err

    pymysql.err.error_map[4025] = pymysql.err.IntegrityError
    pymysql.err.error_map[3819] = pymysql.err.IntegrityError
