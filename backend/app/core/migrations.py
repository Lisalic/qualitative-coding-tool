"""Bring the database schema to Alembic head when the app starts.

Deploys used to rely on ``Base.metadata.create_all`` at startup, which
only ever creates missing *tables* -- a new column on an existing table
(``users.password_reset_requested_at``) reached production code before
it reached the production database, and every query on ``users`` failed.
Running the migration chain on startup makes "deployed" and "migrated"
the same event.

A database that ``create_all`` built and Alembic never tracked (tables,
but no ``alembic_version`` row) is not upgraded: the chain would start by
re-creating ``users``. Instead its drift from the ORM is logged, read-only,
so it can be reconciled deliberately.
"""

import re
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"


def sync_database_url() -> str:
    """``backend.app.database.DATABASE_URL`` with the sync driver pinned:
    a bare ``postgresql://`` resolves to psycopg (v3) on SQLAlchemy >= 2.1,
    which isn't installed -- psycopg2-binary is the sync driver in
    backend/requirements.txt. Read at call time so tests can repoint it.
    """
    from backend.app import database

    return re.sub(
        r"^postgres(?:ql)?(?:\+[^:/]+)?://", "postgresql+psycopg2://", database.DATABASE_URL.strip(), count=1
    )


def alembic_config() -> Config:
    """An Alembic config for the app's own migration chain.

    Built without ``alembic.ini`` on purpose: ``env.py`` only calls
    ``logging.config.fileConfig`` when a config file is set, and that
    would disable every logger the app has already configured. The
    database URL comes from ``env.py`` itself (``sync_database_url``).
    """
    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    return cfg


def upgrade_to_head() -> None:
    """Apply every pending migration. Blocking -- run it off the event loop.

    An untracked existing schema is reported instead (see
    ``report_untracked_schema``) and left untouched.
    """
    if report_untracked_schema():
        return
    command.upgrade(alembic_config(), "head")


def report_untracked_schema() -> bool:
    """If the database has tables but no Alembic revision, log how it
    differs from the ORM and return True. Read-only.
    """
    engine = create_engine(sync_database_url(), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            if not _is_untracked_existing_schema(connection):
                return False
            _log_schema_drift(connection)
            connection.rollback()
            return True
    finally:
        engine.dispose()


def _is_untracked_existing_schema(connection: Connection) -> bool:
    inspector = inspect(connection)
    if not inspector.has_table("users"):
        return False
    if not inspector.has_table("alembic_version"):
        return True
    return connection.execute(text("SELECT version_num FROM alembic_version")).first() is None


def _log_schema_drift(connection: Connection) -> None:
    from backend.app.database import Base
    from backend.app import storage_models, versioning_models  # noqa: F401
    from backend.app.jobs import models as jobs_models  # noqa: F401

    diffs = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    changes = [change for diff in diffs for change in (diff if isinstance(diff, list) else [diff])]
    logger.error(
        "Database has tables but no Alembic revision, so migrations were not run. "
        "%d difference(s) from the ORM follow.",
        len(changes),
    )
    for change in changes:
        logger.error("Schema drift: %s", _describe(change))

    rows = connection.execute(
        text(
            "SELECT c.relname, c.reltuples::bigint FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY c.relname"
        )
    ).all()
    logger.error("Schema drift: estimated rows %s", ", ".join(f"{name}={count}" for name, count in rows))


def _describe(change: tuple) -> str:
    kind = change[0]
    if kind in ("add_table", "remove_table"):
        table = change[1]
        columns = ", ".join(
            f"{c.name} {c.type}{'' if c.nullable else ' NOT NULL'}" for c in table.columns
        )
        return f"{kind} {table.name} ({columns})"
    if kind in ("add_column", "remove_column"):
        _, _, table_name, column = change
        return (
            f"{kind} {table_name}.{column.name} {column.type}"
            f"{'' if column.nullable else ' NOT NULL'}"
            f"{' has-default' if column.server_default is not None else ''}"
        )
    if kind in ("add_index", "remove_index"):
        index = change[1]
        columns = ", ".join(c.name for c in index.columns)
        return f"{kind} {index.name} on {index.table.name}({columns}){' unique' if index.unique else ''}"
    if kind.startswith("modify_"):
        _, _, table_name, column_name, _, existing, new = change
        return f"{kind} {table_name}.{column_name}: database={existing!r} orm={new!r}"
    return repr(change)[:500]
