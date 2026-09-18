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
            job_columns = {c["name"] for c in inspector.get_columns("jobs")}
            coding_entries_columns = {c["name"] for c in inspector.get_columns("coding_entries")}
        finally:
            engine.dispose()

        # Every table this project's ORM models declare should exist --
        # including versioning tables and jobs columns added in recovery.
        for expected in (
            "users", "projects", "files", "file_tables", "project_files",
            "artifact_edges", "prompts", "submissions", "comments",
            "artifact_versions", "coding_entries", "jobs",
            "codebook_codes", "artifact_assists", "row_memos",
        ):
            assert expected in tables, f"{expected!r} missing after upgrade head from empty"

        assert {"accounting", "salvaged_output"} <= job_columns
        # d1f4a8c2e6b9's two additions: per-quote coder attribution.
        assert {"coder", "coder_model"} <= coding_entries_columns


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
            job_columns = {c["name"] for c in inspector.get_columns("jobs")}
        finally:
            engine.dispose()
        assert "coding_entries" in tables
        assert "users" in tables
        assert {"accounting", "salvaged_output"} <= job_columns

    def test_downgrade_one_step_then_upgrade(self, alembic_config, alembic_db_url):
        """A partial round-trip (`downgrade -1` / `upgrade head`) also
        works -- catches a revision whose downgrade() is only correct
        when run all the way to base, not as a single step.
        """
        command.upgrade(alembic_config, "head")
        # Head is e8a2b3c4d5f6 (add jobs.accounting and jobs.salvaged_output).
        # Downgrading 1 step must drop those columns.
        command.downgrade(alembic_config, "-1")

        engine = create_engine(alembic_db_url)
        try:
            inspector = inspect(engine)
            columns_after_downgrade = {c["name"] for c in inspector.get_columns("jobs")}
        finally:
            engine.dispose()
        assert "accounting" not in columns_after_downgrade
        assert "salvaged_output" not in columns_after_downgrade

        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            inspector = inspect(engine)
            columns_after_upgrade = {c["name"] for c in inspector.get_columns("jobs")}
        finally:
            engine.dispose()
        assert {"accounting", "salvaged_output"} <= columns_after_upgrade


class TestSchemaMatchesOrmMetadata:
    def test_migrated_schema_matches_orm_metadata(self, alembic_config, alembic_db_url):
        """After `upgrade head`, the real database structure matches
        `Base.metadata` exactly (modulo the named, pre-existing drift
        allowlist) -- the test that would have caught every prior
        instance of "added an ORM column, forgot the Alembic revision",
        which is exactly how this project's migration chain fell out of
        sync with its schema in the first place.

        Regression: this used to import `storage_models`/`jobs.models`
        but not `versioning_models` -- so unless some OTHER test module
        happened to have imported it first during the same pytest
        collection (an accident of import order, not a guarantee),
        `ArtifactVersion`/`ArtifactEdge`/`CodebookCode`/`ArtifactAssist`
        were never registered on `Base.metadata` and this test silently
        never compared `artifact_versions`/`artifact_edges`/
        `codebook_codes`/`artifact_assists` against the migrated schema
        at all -- a false "0 drift" for exactly the tables added by this
        campaign's own migrations. Running this file in isolation
        reproduced it: `Base.metadata.tables` came back without any of
        those four tables.
        """
        from backend.app.database import Base
        from backend.app import storage_models  # noqa: F401
        from backend.app import versioning_models  # noqa: F401
        from backend.app.jobs import models as jobs_models  # noqa: F401

        assert "artifact_versions" in Base.metadata.tables
        assert "artifact_assists" in Base.metadata.tables
        assert "codebook_codes" in Base.metadata.tables

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
                result = conn.execute(
                    text(
                        "SELECT column_name, generation_expression "
                        "FROM information_schema.columns "
                        "WHERE table_name = 'submissions' "
                        "  AND column_name = 'word_count'"
                    )
                ).one()
                assert result[0] == "word_count"
                assert result[1] is not None
                assert "regexp_replace" in result[1] or "regexp_split_to_array" in result[1]

                user_id = conn.execute(
                    text("INSERT INTO users (email, hashed_password) VALUES ('gen@x.com', 'x') RETURNING id")
                ).scalar_one()
                file_id = conn.execute(
                    text(
                        "INSERT INTO files (filename, schemaname, file_type, user_id) "
                        "VALUES ('f', 'raw_f', 'raw_data', :u) RETURNING id"
                    ),
                    {"u": user_id},
                ).scalar_one()
                sub_id = conn.execute(
                    text(
                        "INSERT INTO submissions (file_id, id, title, selftext, valid_from) "
                        "VALUES (:f, 'sub_1', 'One two three', 'four five', 1) RETURNING pk"
                    ),
                    {"f": file_id},
                ).scalar_one()

                count = conn.execute(
                    text("SELECT word_count FROM submissions WHERE pk = :pk"),
                    {"pk": sub_id},
                ).scalar_one()
                assert count == 5, f"word_count didn't compute as expected: got {count}"
                conn.commit()
        finally:
            engine.dispose()


class TestExistingDatabaseNoOp:
    def test_upgrade_head_is_noop_for_a_db_already_stamped_at_head(
        self, alembic_config, alembic_db_url
    ):
        """Simulates every real deployment's database: schema built and stamped
        at head. Upgrading to head against it should apply zero revisions.
        """
        from backend.app.database import Base
        from backend.app import storage_models  # noqa: F401
        from backend.app.jobs import models as jobs_models  # noqa: F401

        engine = create_engine(alembic_db_url)
        try:
            Base.metadata.create_all(engine)
        finally:
            engine.dispose()

        command.stamp(alembic_config, "head")

        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            with engine.connect() as conn:
                current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        finally:
            engine.dispose()
        assert current == "e8a2b3c4d5f6", "expected upgrade head to stay at stamped head"
