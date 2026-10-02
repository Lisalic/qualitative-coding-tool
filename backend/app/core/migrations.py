"""Bring the database schema to Alembic head when the app starts.

Deploys used to rely on ``Base.metadata.create_all`` at startup, which
only ever creates missing *tables* -- a new column on an existing table
(``users.password_reset_requested_at``) reached production code before
it reached the production database, and every query on ``users`` failed.
Running the migration chain on startup makes "deployed" and "migrated"
the same event.

A database that ``create_all`` built and Alembic never tracked (tables,
but no ``alembic_version`` row -- production's case) can't be upgraded:
the chain would start by re-creating ``users``, and every table a later
revision reshaped (``coding_entries``, ``submissions``/``comments``,
``jobs``) is still in its first shape. It is rebuilt once instead -- see
``_rebuild_untracked_schema``.
"""

import re
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"

# Arbitrary app-wide key for the Postgres advisory lock that serializes
# migrations across processes (an overlapping deploy can boot a new
# container before the old one stops).
MIGRATION_LOCK_KEY = 7_206_001

# What survives rebuilding an untracked schema: accounts and what hangs
# directly off them. Parents first, so foreign keys hold on restore.
KEPT_TABLES = ("users", "projects", "prompts")


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


def lock_for_migrations(connection: Connection) -> None:
    """Take the session-level migration lock (Postgres only). It outlives
    the commit and is released when the connection closes; a second
    migrator then finds the work already done.
    """
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        connection.commit()


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
    """Apply every pending migration -- rebuilding an untracked schema
    first -- in one transaction, so a failure leaves the database as it
    was. Blocking; run it off the event loop.
    """
    engine = create_engine(sync_database_url(), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            lock_for_migrations(connection)
            cfg = alembic_config()
            # env.py runs on this connection: inside this transaction, and
            # already holding the lock.
            cfg.attributes["connection"] = connection
            with connection.begin():
                if _is_untracked_existing_schema(connection):
                    _rebuild_untracked_schema(connection, cfg)
                else:
                    command.upgrade(cfg, "head")
    finally:
        engine.dispose()


def _is_untracked_existing_schema(connection: Connection) -> bool:
    inspector = inspect(connection)
    if not inspector.has_table("users"):
        return False
    if not inspector.has_table("alembic_version"):
        return True
    return connection.execute(text("SELECT version_num FROM alembic_version")).first() is None


def _rebuild_untracked_schema(connection: Connection, cfg: Config) -> None:
    """Drop the untracked schema and build head from the migration chain,
    carrying over the rows of ``KEPT_TABLES``.

    Everything else -- files and every artifact table -- is dropped. On
    the one database this was written for (production, built only by
    ``create_all``), those tables were never reshaped by the revisions the
    code depends on, so the features writing them could not have worked;
    the project carries no production data worth migrating (CLAUDE.md).
    """
    from backend.app.database import Base
    from backend.app import storage_models, versioning_models  # noqa: F401
    from backend.app.jobs import models as jobs_models  # noqa: F401

    _log_schema_drift(connection, Base.metadata)

    inspector = inspect(connection)
    kept: dict[str, list[dict]] = {}
    for name in KEPT_TABLES:
        table = Base.metadata.tables[name]
        existing = {c["name"] for c in inspector.get_columns(name)} if inspector.has_table(name) else set()
        columns = [c for c in table.columns if c.name in existing]
        kept[name] = [dict(row) for row in connection.execute(select(*columns)).mappings()] if columns else []

    dropped = inspector.get_table_names()
    for name in dropped:
        connection.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))

    command.upgrade(cfg, "head")

    for name in KEPT_TABLES:
        if kept[name]:
            connection.execute(Base.metadata.tables[name].insert(), kept[name])
        connection.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                f'COALESCE((SELECT MAX(id) FROM "{name}"), 1), '
                f'(SELECT MAX(id) FROM "{name}") IS NOT NULL)'
            )
        )

    logger.warning(
        "Rebuilt the untracked database schema at Alembic head: dropped %s; kept %s",
        ", ".join(sorted(dropped)),
        ", ".join(f"{name}={len(rows)}" for name, rows in kept.items()),
    )


def _log_schema_drift(connection: Connection, metadata) -> None:
    diffs = compare_metadata(MigrationContext.configure(connection), metadata)
    changes = [change for diff in diffs for change in (diff if isinstance(diff, list) else [diff])]
    logger.warning(
        "Database has tables but no Alembic revision; rebuilding it. %d difference(s) from the ORM follow.",
        len(changes),
    )
    for change in changes:
        logger.warning("Schema drift: %s", _describe(change))


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
