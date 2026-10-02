"""Tests for backend/app/core/migrations.py and the startup hook that runs it.

Running the chain itself needs a real Postgres -- that lives in
tests/backend/integration/test_alembic_migration.py::TestStartupUpgrade.
"""

import logging
from unittest.mock import AsyncMock

from alembic import command
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from backend.app.core import migrations
from backend.app.main import app as fastapi_app


class TestAlembicConfig:
    def test_points_at_the_repo_migration_chain(self) -> None:
        cfg = migrations.alembic_config()
        assert (migrations.ALEMBIC_DIR / "env.py").is_file()
        assert ScriptDirectory.from_config(cfg).get_heads() == ["b8d4f2a6c1e7"]

    def test_has_no_ini_file_so_env_py_leaves_app_logging_alone(self) -> None:
        # env.py calls logging.config.fileConfig only when a file is set,
        # and fileConfig disables every already-configured logger.
        assert migrations.alembic_config().config_file_name is None


class TestEnvPyDatabaseUrl:
    def test_percent_encoded_password_reaches_alembic_intact(self, monkeypatch, capsys) -> None:
        # Production's password is URL-encoded; Alembic's ConfigParser read
        # the bare `%` as interpolation and env.py raised before connecting.
        # Offline (`sql=True`) runs env.py end to end without a database.
        url = "postgresql://app:p%40ss%25w0rd@db.example.com:5432/prod"
        monkeypatch.setattr("backend.app.database.DATABASE_URL", url)
        cfg = migrations.alembic_config()

        command.upgrade(cfg, "a1e6f2c9b3d7", sql=True)

        assert cfg.get_main_option("sqlalchemy.url") == (
            "postgresql+psycopg2://app:p%40ss%25w0rd@db.example.com:5432/prod"
        )
        assert "CREATE TABLE users" in capsys.readouterr().out


def _stub_startup(monkeypatch, upgrade) -> list[str]:
    calls: list[str] = []

    def fake_upgrade() -> None:
        calls.append("upgrade")
        upgrade()

    async def fake_reconcile() -> int:
        calls.append("reconcile")
        return 0

    async def no_refresh() -> None:
        return None

    monkeypatch.setattr("backend.app.main.upgrade_to_head", fake_upgrade)
    monkeypatch.setattr("backend.app.main.reconcile_orphaned_jobs_on_startup", AsyncMock(side_effect=fake_reconcile))
    monkeypatch.setattr("backend.app.main._refresh_model_catalog_loop", no_refresh)
    return calls


class TestStartupRunsMigrations:
    def test_upgrades_before_touching_the_database(self, monkeypatch) -> None:
        calls = _stub_startup(monkeypatch, lambda: None)

        with TestClient(fastapi_app) as client:
            assert client.get("/").status_code == 200

        assert calls == ["upgrade", "reconcile"]

    def test_failed_upgrade_is_logged_and_the_app_still_serves(self, monkeypatch, caplog) -> None:
        def boom() -> None:
            raise RuntimeError("relation already exists")

        calls = _stub_startup(monkeypatch, boom)

        with caplog.at_level(logging.ERROR, logger="backend.app.main"):
            with TestClient(fastapi_app) as client:
                assert client.get("/").status_code == 200

        assert calls == ["upgrade", "reconcile"]
        failures = [r for r in caplog.records if "migration to Alembic head failed" in r.getMessage()]
        assert len(failures) == 1
        assert failures[0].exc_info is not None
