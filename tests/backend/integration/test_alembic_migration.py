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
        # Head is b8d4f2a6c1e7 (unique index on lower(users.email)).
        # Downgrading 1 step must drop that index.
        command.downgrade(alembic_config, "-1")

        engine = create_engine(alembic_db_url)
        try:
            indexes_after_downgrade = {i["name"] for i in inspect(engine).get_indexes("users")}
        finally:
            engine.dispose()
        assert "uq_users_email_lower" not in indexes_after_downgrade

        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_db_url)
        try:
            columns_after_upgrade = {c["name"] for c in inspect(engine).get_columns("users")}
        finally:
            engine.dispose()
        assert "password_reset_requested_at" in columns_after_upgrade


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
        assert current == "b8d4f2a6c1e7", "expected upgrade head to stay at stamped head"


def _version(db_url: str) -> str:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()


def _user_columns(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    try:
        return {c["name"] for c in inspect(engine).get_columns("users")}
    finally:
        engine.dispose()


def _production_state(alembic_config, db_url: str) -> None:
    """The database as the deploy that shipped `f4c8b2a1e0d3`/`a7c3e5f19b20`
    left it: stamped one revision short of both, with `starred_quotes`
    already created by the startup `create_all` that deploy still ran, and
    `users` still missing `password_reset_requested_at`.
    """
    from backend.app.database import Base
    from backend.app import storage_models, versioning_models  # noqa: F401
    from backend.app.jobs import models as jobs_models  # noqa: F401

    command.upgrade(alembic_config, "e8a2b3c4d5f6")
    engine = create_engine(db_url)
    try:
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(
                text("INSERT INTO users (email, hashed_password) VALUES ('existing@x.com', 'x')")
            )
            conn.commit()
        assert inspect(engine).has_table("starred_quotes")
    finally:
        engine.dispose()
    assert "password_reset_requested_at" not in _user_columns(db_url)


class TestStartupUpgrade:
    """`backend.app.core.migrations.upgrade_to_head`, which the app runs on
    every startup in place of `Base.metadata.create_all`.
    """

    def test_builds_an_empty_database_and_is_idempotent(self, alembic_config, alembic_db_url):
        from backend.app.core.migrations import upgrade_to_head

        upgrade_to_head()
        assert _version(alembic_db_url) == "b8d4f2a6c1e7"
        upgrade_to_head()
        assert _version(alembic_db_url) == "b8d4f2a6c1e7"

    def test_recovers_the_production_state(self, alembic_config, alembic_db_url):
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from backend.app.core.migrations import upgrade_to_head
        from backend.app.database import User

        _production_state(alembic_config, alembic_db_url)

        upgrade_to_head()

        assert _version(alembic_db_url) == "b8d4f2a6c1e7"
        assert "password_reset_requested_at" in _user_columns(alembic_db_url)
        # The exact query production 500'd on.
        engine = create_engine(alembic_db_url)
        try:
            with Session(engine) as session:
                user = session.execute(select(User).where(User.email == "existing@x.com")).scalar_one()
                assert user.password_reset_requested_at is None
        finally:
            engine.dispose()

    def test_adopts_a_column_added_by_hand(self, alembic_config, alembic_db_url):
        from backend.app.core.migrations import upgrade_to_head

        command.upgrade(alembic_config, "f4c8b2a1e0d3")
        engine = create_engine(alembic_db_url)
        try:
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                    "password_reset_requested_at TIMESTAMP WITH TIME ZONE"
                ))
                conn.commit()
        finally:
            engine.dispose()

        upgrade_to_head()

        assert _version(alembic_db_url) == "b8d4f2a6c1e7"

    def test_concurrent_upgrades_are_serialized(self, alembic_config, alembic_db_url):
        """Two containers booting at once (an overlapping deploy) must not
        race each other through the chain. Separate processes, as in
        production -- Alembic's `context` is process-global, so threads in
        one process can't stand in for this.
        """
        import subprocess
        import sys

        env = {**os.environ, "DATABASE_URL": alembic_db_url}
        script = "from backend.app.core.migrations import upgrade_to_head; upgrade_to_head()"
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            for _ in range(4)
        ]
        outputs = [proc.communicate(timeout=120)[0].decode() for proc in procs]

        assert [proc.returncode for proc in procs] == [0] * len(procs), "\n\n".join(outputs)
        assert _version(alembic_db_url) == "b8d4f2a6c1e7"

    def test_password_with_url_encoded_characters(self, alembic_config, alembic_db_url, monkeypatch):
        """Production's password percent-encodes to a URL full of `%`, which
        Alembic's ConfigParser used to choke on before ever connecting.
        """
        import uuid
        from urllib.parse import quote, urlsplit, urlunsplit

        from backend.app import database as db_module
        from backend.app.core.migrations import upgrade_to_head

        role = f"qc_pct_{uuid.uuid4().hex[:8]}"
        password = "p@ss%w0rd:/?"
        admin = create_engine(alembic_db_url, isolation_level="AUTOCOMMIT")
        try:
            with admin.connect() as conn:
                conn.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD :pw"), {"pw": password})
                conn.execute(text(f"GRANT ALL ON SCHEMA public TO {role}"))

            parts = urlsplit(alembic_db_url)
            host = parts.netloc.rsplit("@", 1)[-1]
            role_url = urlunsplit(
                ("postgresql", f"{role}:{quote(password, safe='')}@{host}", parts.path, "", "")
            )
            assert "%" in role_url
            monkeypatch.setattr(db_module, "DATABASE_URL", role_url)

            upgrade_to_head()

            assert _version(alembic_db_url) == "b8d4f2a6c1e7"
        finally:
            with admin.connect() as conn:
                conn.execute(text(f"DROP OWNED BY {role}"))
                conn.execute(text(f"DROP ROLE {role}"))
            admin.dispose()

    def test_leaves_app_loggers_enabled(self, alembic_config, alembic_db_url):
        import logging

        from backend.app.core.migrations import upgrade_to_head

        # Other tests here go through `alembic.ini`, whose fileConfig has
        # already disabled every existing logger -- start from enabled.
        app_logger = logging.getLogger("backend.app.main")
        app_logger.disabled = False

        upgrade_to_head()

        assert app_logger.disabled is False


# The schema drift production's startup logged on 2026-10-02 (sorted): a
# database `create_all` built and Alembic never tracked. `_prod_replica`
# must reproduce it exactly.
PRODUCTION_DRIFT = [
    'add_column coding_entries.code_uid VARCHAR NOT NULL',
    'add_column coding_entries.coder VARCHAR NOT NULL has-default',
    'add_column coding_entries.coder_model VARCHAR',
    'add_column coding_entries.end_offset INTEGER NOT NULL',
    'add_column coding_entries.id INTEGER NOT NULL',
    'add_column coding_entries.notes TEXT',
    'add_column coding_entries.quote TEXT NOT NULL',
    'add_column coding_entries.row_type VARCHAR NOT NULL has-default',
    'add_column coding_entries.start_offset INTEGER NOT NULL',
    'add_column coding_entries.valid_from INTEGER NOT NULL has-default',
    'add_column coding_entries.valid_to INTEGER',
    'add_column comments.pk INTEGER NOT NULL',
    'add_column comments.valid_from INTEGER NOT NULL has-default',
    'add_column comments.valid_to INTEGER',
    'add_column jobs.accounting JSON',
    'add_column jobs.progress JSON',
    'add_column jobs.salvaged_output JSON',
    'add_column submissions.pk INTEGER NOT NULL',
    'add_column submissions.valid_from INTEGER NOT NULL has-default',
    'add_column submissions.valid_to INTEGER',
    'add_column users.password_reset_requested_at DATETIME',
    'add_index idx_coding_entries_file_id_code_uid on coding_entries(file_id, code_uid)',
    'add_index idx_coding_entries_file_id_coder on coding_entries(file_id, coder)',
    'add_index idx_coding_entries_file_id_row on coding_entries(file_id, row_type, post_id)',
    'add_index idx_coding_entries_live on coding_entries(file_id, valid_to)',
    'add_index idx_comments_live on comments(file_id, valid_to)',
    'add_index idx_submissions_live on submissions(file_id, valid_to)',
    'add_index uq_comments_file_id_id_live on comments(file_id, id) unique',
    'add_index uq_submissions_file_id_id_live on submissions(file_id, id) unique',
    'add_index uq_users_email_lower on users(email) unique',
    'remove_column coding_entries.evidence TEXT',
    'remove_column files.systemprompt VARCHAR',
    'remove_column files.userprompt VARCHAR',
    'remove_table artifact_content (file_id INTEGER NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP)',
    'remove_table file_dependencies (id INTEGER NOT NULL, child_file_id INTEGER NOT NULL, parent_file_id INTEGER NOT NULL, created_at TIMESTAMP)',
]


def _prod_replica(alembic_config, db_url: str, *, empty_version_table: bool = False) -> None:
    """Production's schema, rebuilt: the chain only ever reached
    `8b0a568ce28c`, every later table came from `create_all` in its final
    shape, and Alembic's own bookkeeping is gone. Seeded with accounts and
    with rows in the tables that get dropped.
    """
    from backend.app.api.utils import _hash_password
    from backend.app.database import Base
    from backend.app import storage_models, versioning_models  # noqa: F401
    from backend.app.jobs import models as jobs_models  # noqa: F401

    command.upgrade(alembic_config, "8b0a568ce28c")
    engine = create_engine(db_url)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE alembic_version"))
            if empty_version_table:
                conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(
                text("INSERT INTO users (id, email, hashed_password) VALUES (5, 'ana@x.com', :a), (9, 'bo@x.com', :b)"),
                {"a": _hash_password("ana-pass"), "b": _hash_password("bo-pass")},
            )
            conn.execute(text("INSERT INTO projects (id, user_id, projectname, description) VALUES (3, 5, 'Thesis', 'ch. 2')"))
            conn.execute(text("INSERT INTO prompts (id, user_id, promptname, prompt, type) VALUES (7, 9, 'P', 'Find themes', 'filter')"))
            conn.execute(text(
                "INSERT INTO files (id, user_id, filename, schemaname, file_type, systemprompt) "
                "VALUES (11, 5, 'dump.zst', 'proj_ab12', 'raw_data', 'old')"
            ))
            conn.execute(text("INSERT INTO project_files (project_id, file_id) VALUES (3, 11)"))
            conn.execute(text("INSERT INTO submissions (file_id, id, title) VALUES (11, 's1', 'One'), (11, 's2', 'Two')"))
            conn.execute(text("INSERT INTO coding_entries (file_id, post_id, code, evidence) VALUES (11, 's1', 'Trust', 'x')"))
            conn.execute(text("INSERT INTO artifact_content (file_id, content) VALUES (11, 'old blob')"))
    finally:
        engine.dispose()


def _drift(db_url: str) -> list[str]:
    from backend.app.core.migrations import _describe
    from backend.app.database import Base

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    return sorted(_describe(c) for d in diffs for c in (d if isinstance(d, list) else [d]))


def _rows(db_url: str, sql: str) -> list[tuple]:
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            return [tuple(r) for r in conn.execute(text(sql)).all()]
    finally:
        engine.dispose()


def _public_tables(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


_KEPT_ROWS_SQL = {
    "users": "SELECT id, email, hashed_password, created_at FROM users ORDER BY id",
    "projects": "SELECT id, user_id, projectname, description, created_at FROM projects ORDER BY id",
    "prompts": "SELECT id, user_id, promptname, prompt, type FROM prompts ORDER BY id",
}


class TestUntrackedSchemaRebuild:
    """`upgrade_to_head` against production's real shape: a schema Alembic
    never tracked. Rebuilt at head, keeping users/projects/prompts.
    """

    def test_replica_matches_production(self, alembic_config, alembic_db_url):
        _prod_replica(alembic_config, alembic_db_url)
        assert _drift(alembic_db_url) == PRODUCTION_DRIFT

    @pytest.mark.parametrize("empty_version_table", [False, True])
    def test_rebuilds_at_head_keeping_accounts(
        self, alembic_config, alembic_db_url, caplog, empty_version_table
    ):
        import logging

        from backend.app.core.migrations import upgrade_to_head

        _prod_replica(alembic_config, alembic_db_url, empty_version_table=empty_version_table)
        kept_before = {t: _rows(alembic_db_url, q) for t, q in _KEPT_ROWS_SQL.items()}
        # `_prod_replica` ran Alembic through `alembic.ini`, whose fileConfig
        # replaces the root handlers (caplog's included) and disables
        # existing loggers -- capture on the module's own logger instead.
        migrations_logger = logging.getLogger("backend.app.core.migrations")
        migrations_logger.disabled = False
        migrations_logger.addHandler(caplog.handler)
        try:
            upgrade_to_head()
        finally:
            migrations_logger.removeHandler(caplog.handler)

        assert _version(alembic_db_url) == "b8d4f2a6c1e7"
        assert _drift(alembic_db_url) == []
        assert {t: _rows(alembic_db_url, q) for t, q in _KEPT_ROWS_SQL.items()} == kept_before
        assert kept_before["users"] and kept_before["projects"] and kept_before["prompts"]
        for table in ("files", "project_files", "submissions", "coding_entries"):
            assert _rows(alembic_db_url, f"SELECT count(*) FROM {table}") == [(0,)]
        assert not {"artifact_content", "file_dependencies"} & _public_tables(alembic_db_url)
        assert any("Rebuilt the untracked database schema" in r.getMessage() for r in caplog.records)

        # Sequences continue past the restored ids.
        assert _rows(
            alembic_db_url,
            "INSERT INTO users (email, hashed_password) VALUES ('new@x.com', 'x') RETURNING id",
        ) == [(10,)]

    def test_a_failure_leaves_the_database_untouched(self, alembic_config, alembic_db_url, monkeypatch):
        from backend.app.core import migrations

        _prod_replica(alembic_config, alembic_db_url)
        tables_before = _public_tables(alembic_db_url)
        users_before = _rows(alembic_db_url, _KEPT_ROWS_SQL["users"])
        real_upgrade = migrations.command.upgrade

        def upgrade_then_fail(cfg, revision):
            real_upgrade(cfg, revision)
            raise RuntimeError("simulated failure after the schema was rebuilt")

        monkeypatch.setattr(migrations.command, "upgrade", upgrade_then_fail)
        with pytest.raises(RuntimeError, match="simulated failure"):
            migrations.upgrade_to_head()

        assert _public_tables(alembic_db_url) == tables_before
        assert _rows(alembic_db_url, _KEPT_ROWS_SQL["users"]) == users_before
        assert _rows(alembic_db_url, "SELECT count(*) FROM submissions") == [(2,)]
        assert _drift(alembic_db_url) == PRODUCTION_DRIFT

    def test_runs_once(self, alembic_config, alembic_db_url):
        from backend.app.core.migrations import upgrade_to_head

        _prod_replica(alembic_config, alembic_db_url)
        upgrade_to_head()
        _rows(
            alembic_db_url,
            "INSERT INTO files (user_id, filename, schemaname, file_type) "
            "VALUES (5, 'after.zst', 'proj_cd34', 'raw_data') RETURNING id",
        )

        upgrade_to_head()

        assert _rows(alembic_db_url, "SELECT filename FROM files") == [("after.zst",)]

    def test_concurrent_starts_rebuild_once(self, alembic_config, alembic_db_url):
        import subprocess
        import sys

        _prod_replica(alembic_config, alembic_db_url)
        env = {**os.environ, "DATABASE_URL": alembic_db_url}
        script = (
            "import logging; logging.basicConfig(level=logging.WARNING); "
            "from backend.app.core.migrations import upgrade_to_head; upgrade_to_head()"
        )
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            for _ in range(4)
        ]
        outputs = [proc.communicate(timeout=180)[0].decode() for proc in procs]

        assert [proc.returncode for proc in procs] == [0] * len(procs), "\n\n".join(outputs)
        assert sum("Rebuilt the untracked database schema" in out for out in outputs) == 1, outputs
        assert _version(alembic_db_url) == "b8d4f2a6c1e7"
        assert [r[1] for r in _rows(alembic_db_url, _KEPT_ROWS_SQL["users"])] == ["ana@x.com", "bo@x.com"]


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _RunningApp:
    """The real app, booted the way Azure does (`python -m uvicorn
    backend.app.main:app`) against `db_url`.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

    def __enter__(self) -> str:
        import subprocess
        import sys
        import time

        import httpx

        port = _free_port()
        env = {**os.environ, "DATABASE_URL": self.db_url, "JWT_SECRET_KEY": "integration-secret"}
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", str(port)],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 60
        while True:
            assert self.proc.poll() is None, self.proc.stdout.read().decode()
            try:
                if httpx.get(f"{base}/", timeout=1).status_code == 200:
                    return base
            except httpx.HTTPError:
                pass
            assert time.monotonic() < deadline, "app did not start within 60s"
            time.sleep(0.25)

    def __exit__(self, *exc) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=15)


def _assert_auth_works(base: str) -> None:
    import httpx

    unknown = httpx.post(f"{base}/api/login/", json={"email": "nobody@x.com", "password": "pw"})
    assert unknown.status_code == 401, unknown.text

    registered = httpx.post(f"{base}/api/register/", json={"email": "new@x.com", "password": "secret123"})
    assert registered.status_code == 200, registered.text

    logged_in = httpx.post(f"{base}/api/login/", json={"email": "new@x.com", "password": "secret123"})
    assert logged_in.status_code == 200, logged_in.text

    token = logged_in.json()["access_token"]
    me = httpx.get(f"{base}/api/me/", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text


class TestAppBootsOnProductionState:
    def test_tracked_database_one_revision_behind(self, alembic_config, alembic_db_url):
        """Stamped one revision short, with the table that deploy's
        `create_all` made: login (unknown and known user), register, /me.
        """
        _production_state(alembic_config, alembic_db_url)

        with _RunningApp(alembic_db_url) as base:
            assert _version(alembic_db_url) == "b8d4f2a6c1e7"
            _assert_auth_works(base)

    def test_untracked_production_replica(self, alembic_config, alembic_db_url):
        """Production's actual shape on 2026-10-02: an existing account
        still logs in with its password after the rebuild, and the
        features that write the rebuilt tables work.
        """
        import httpx

        _prod_replica(alembic_config, alembic_db_url)

        with _RunningApp(alembic_db_url) as base:
            assert _version(alembic_db_url) == "b8d4f2a6c1e7"
            _assert_auth_works(base)

            ana = httpx.post(f"{base}/api/login/", json={"email": "ana@x.com", "password": "ana-pass"})
            assert ana.status_code == 200, ana.text
            headers = {"Authorization": f"Bearer {ana.json()['access_token']}"}
            projects = httpx.get(f"{base}/api/projects/", headers=headers)
            assert projects.status_code == 200, projects.text
            assert [p["projectname"] for p in projects.json()["projects"]] == ["Thesis"]
