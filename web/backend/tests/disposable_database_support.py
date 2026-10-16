"""Fail closed before any autocommitted fixture writes in SQL rehearsals."""

import psycopg
from psycopg.conninfo import conninfo_to_dict

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def connect_disposable_database(dsn, *, markers, autocommit=True):
    try:
        parameters = conninfo_to_dict(dsn)
    except Exception:
        raise RuntimeError("Invalid disposable database configuration") from None
    if (parameters.get("host") not in LOOPBACK_HOSTS or parameters.get("service")
            or parameters.get("hostaddr", "127.0.0.1") not in {"127.0.0.1", "::1"}):
        raise RuntimeError("SQL rehearsal requires an explicit loopback database")
    connection = None
    try:
        # Pin the effective address too: ambient PGHOSTADDR must not redirect
        # an apparently loopback host to a different server.
        address = parameters.get("hostaddr") or ("::1" if parameters["host"] == "::1" else "127.0.0.1")
        connection = psycopg.connect(dsn, hostaddr=address, autocommit=True, connect_timeout=5)
        marker = connection.execute(
            "select pg_catalog.shobj_description(oid,'pg_database') "
            "from pg_catalog.pg_database where datname=current_database()"
        ).fetchone()
        if not marker or marker[0] not in markers:
            raise RuntimeError("Database is not marked for this disposable rehearsal")
        connection.autocommit = autocommit
        return connection
    except Exception:
        if connection is not None:
            connection.close()
        # Provider exceptions can contain credentials or connection strings.
        raise RuntimeError("Disposable database ownership verification failed") from None
