"""Integration tests for the Alembic migration chain itself.

Everything else in this suite exercises the ORM schema built by
`Base.metadata.create_all` (see `conftest.py::integration_sync_engine`) --
these tests are the only place that actually runs `alembic upgrade`/
`downgrade` against a real database, because that is the only way to
verify a migration chain is even internally consistent.

Before `a1e6f2c9b3d7` (the "baseline untracked schema" revision), this
was impossible to test at all: `alembic upgrade head` against a
genuinely empty database failed on the very first revision
(`8b0a568ce28c`, whose `jobs.user_id` column FKs `users.id`, which never
existed independently of `Base.metadata.create_all`). See that
revision's module docstring for the full story and how it was verified
by hand before this test existed to catch it automatically.

Each test gets its OWN dedicated throwaway database (function-scoped),
deliberately not the shared session-scoped one from
`integration_db_url`/`integration_sync_engine` -- those are shared across
the whole integration session and other tests populate them via
`Base.metadata.create_all` directly, which would make "upgrade from a
genuinely empty database" untestable if this file reused them.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from tests.backend.integration.conftest import _admin_url_and_target_db

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Pre-existing drift `8b0a568ce28c`'s docstring already flagged and
# explicitly left out of scope (a stray `project_tables` table, several
# TEXT/String column-type mismatches, a missing `project_files` FK) --
# `a1e6f2c9b3d7`'s docstring repeats the same "out of scope" call. Kept
# here as a named allowlist so `test_migrated_schema_matches_orm_metadata`
# can assert "no *new* drift" rather than "no drift at all", and so any
# addition to this list is a deliberate, reviewed decision rather than a
# silently-passing test.
_KNOWN_PRE_EXISTING_DRIFT: set[str] = set()


@pytest.fixture()
def alembic_db_url():
    """A fresh, empty, function-scoped throwaway database -- created and
    dropped the same way `conftest.py::integration_db_url` does, but not
    shared with any other test.
    """
    admin_url, target_db = _admin_url_and_target_db()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Could not create throwaway alembic-test database: {exc}")
    finally:
        admin_engine.dispose()

    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(admin_url)
    db_url = urlunsplit((parts.scheme, parts.netloc, f"/{target_db}", "", ""))

    yield db_url

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": target_db},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{target_db}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture()
def alembic_config(alembic_db_url, monkeypatch):
    """An Alembic `Config` pointed at this repo's `alembic.ini`, wired to
    `alembic_db_url` instead of the real app database.

    `backend/alembic/env.py` does `from backend.app.database import ...
    DATABASE_URL` and then `config.set_main_option("sqlalchemy.url",
    DATABASE_URL)` on every invocation -- so passing a URL via
    `Config.set_main_option` alone is not enough, env.py would overwrite
    it right back with whatever `backend.app.database.DATABASE_URL`
    currently holds (the fake sentinel `tests/conftest.py` sets at import
    time). `env.py` is re-executed fresh on every `command.upgrade`/
    `downgrade` call (`alembic.script.Script.run_env` ->
    `util.load_python_file`), so monkeypatching the module attribute here
    is picked up on each call.
    """
    from backend.app import database as db_module

    monkeypatch.setattr(db_module, "DATABASE_URL", alembic_db_url)

    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(REPO_ROOT, "backend", "alembic"))
    cfg.set_main_option("sqlalchemy.url", alembic_db_url)
    return cfg


class TestUpgradeFromEmpty:
    def test_upgrade_head_from_empty(self, alembic_config, alembic_db_url):
        """`alembic upgrade head` succeeds against a genuinely empty
        database -- the thing that was impossible before `a1e6f2c9b3d7`.
        """
        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
        finally:
            engine.dispose()

        # Every table this project's ORM models declare should exist --
        # spot-check the ones that were never created by any revision
        # before a1e6f2c9b3d7, plus a couple from the pre-existing chain.
        for expected in (
            "users", "projects", "files", "file_tables", "project_files",
            "file_dependencies", "prompts", "submissions", "comments",
            "artifact_content", "coding_entries", "jobs",
        ):
            assert expected in tables, f"{expected!r} missing after upgrade head from empty"


class TestDowngradeUpgradeRoundTrip:
    def test_downgrade_then_upgrade_round_trip(self, alembic_config, alembic_db_url):
        """`upgrade head` -> `downgrade base` -> `upgrade head` leaves the
        database in the same working state, and downgrading all the way
        to base leaves nothing behind but Alembic's own bookkeeping table.
        """
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")

        engine = create_engine(alembic_db_url)
        try:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
        finally:
            engine.dispose()
        assert tables <= {"alembic_version"}, f"downgrade to base left tables behind: {tables}"

        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
        finally:
            engine.dispose()
        assert "coding_entries" in tables
        assert "users" in tables

    def test_downgrade_one_step_then_upgrade(self, alembic_config, alembic_db_url):
        """A partial round-trip (`downgrade -1` / `upgrade head`) also
        works -- catches a revision whose downgrade() is only correct
        when run all the way to base, not as a single step.
        """
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "-1")
        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            inspector = inspect(engine)
            columns = {c["name"] for c in inspector.get_columns("coding_entries")}
        finally:
            engine.dispose()
        assert {"quote", "start_offset", "end_offset"} <= columns


class TestSchemaMatchesOrmMetadata:
    def test_migrated_schema_matches_orm_metadata(self, alembic_config, alembic_db_url):
        """After `upgrade head`, the real database structure matches
        `Base.metadata` exactly (modulo the named, pre-existing drift
        allowlist) -- the test that would have caught every prior
        instance of "added an ORM column, forgot the Alembic revision",
        which is exactly how this project's migration chain fell out of
        sync with its schema in the first place.
        """
        from backend.app.database import Base
        from backend.app import storage_models  # noqa: F401
        from backend.app.jobs import models as jobs_models  # noqa: F401

        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            with engine.connect() as conn:
                ctx = MigrationContext.configure(conn)
                diff = compare_metadata(ctx, Base.metadata)
        finally:
            engine.dispose()

        unexpected = [d for d in diff if repr(d) not in _KNOWN_PRE_EXISTING_DRIFT]
        assert not unexpected, f"Unallowed schema drift after upgrade head: {unexpected}"


class TestGeneratedWordCountColumn:
    def test_word_count_is_a_generated_column(self, alembic_config, alembic_db_url):
        """`storage_models.py`'s module docstring claims `word_count` is
        backed by a real Postgres `GENERATED ALWAYS AS (...) STORED`
        column -- before `a1e6f2c9b3d7` this was aspirational (no
        revision ever wrote that DDL). Assert it's actually true, and
        that the expression actually computes.
        """
        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            with engine.connect() as conn:
                for table in ("submissions", "comments"):
                    row = conn.execute(
                        text(
                            "SELECT is_generated, generation_expression "
                            "FROM information_schema.columns "
                            "WHERE table_name = :t AND column_name = 'word_count'"
                        ),
                        {"t": table},
                    ).one()
                    assert row.is_generated == "ALWAYS", f"{table}.word_count is not a generated column"
                    assert row.generation_expression, f"{table}.word_count has no generation expression"

                conn.execute(
                    text(
                        "INSERT INTO users (email, hashed_password) VALUES ('t@example.com', 'x')"
                    )
                )
                file_id = conn.execute(
                    text(
                        "INSERT INTO files (user_id, filename, schemaname, file_type) "
                        "VALUES (1, 'f', 'proj_x', 'raw_data') RETURNING id"
                    )
                ).scalar_one()
                conn.execute(
                    text(
                        "INSERT INTO submissions (file_id, id, title, selftext) "
                        "VALUES (:fid, 's1', 'hello world', 'this is a test post')"
                    ),
                    {"fid": file_id},
                )
                word_count = conn.execute(
                    text("SELECT word_count FROM submissions WHERE id = 's1'")
                ).scalar_one()
                assert word_count == 7
                conn.commit()
        finally:
            engine.dispose()


class TestExistingDatabaseNoOp:
    def test_upgrade_head_is_noop_for_a_db_already_stamped_at_old_head(
        self, alembic_config, alembic_db_url
    ):
        """Simulates every real deployment's database: schema built by
        `Base.metadata.create_all` (not Alembic), then stamped at the
        chain's previous head (`9a1c3e7f5b2d`) the way a database that
        ran the real migration history for real would be. Inserting
        `a1e6f2c9b3d7` as a new ROOT ahead of that stamp must not require
        any operator action -- `upgrade head` against it should apply
        zero revisions, per that revision's own docstring claim.
        """
        from backend.app.database import Base
        from backend.app import storage_models  # noqa: F401
        from backend.app.jobs import models as jobs_models  # noqa: F401

        engine = create_engine(alembic_db_url)
        try:
            Base.metadata.create_all(engine)
        finally:
            engine.dispose()

        command.stamp(alembic_config, "9a1c3e7f5b2d")

        # No exception, and specifically: no attempt to re-create any
        # table that create_all already built (which would raise) --
        # `9a1c3e7f5b2d` is still this chain's head, so upgrading "to
        # head" from a database already stamped there applies zero
        # revisions and leaves the stamp unchanged.
        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            with engine.connect() as conn:
                current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        finally:
            engine.dispose()
        assert current == "9a1c3e7f5b2d", "expected upgrade head to be a no-op for an already-stamped db"
