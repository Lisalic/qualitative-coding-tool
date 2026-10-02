"""Bring the database schema to Alembic head when the app starts.

Deploys used to rely on ``Base.metadata.create_all`` at startup, which
only ever creates missing *tables* -- a new column on an existing table
(``users.password_reset_requested_at``) reached production code before
it reached the production database, and every query on ``users`` failed.
Running the migration chain on startup makes "deployed" and "migrated"
the same event.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"


def alembic_config() -> Config:
    """An Alembic config for the app's own migration chain.

    Built without ``alembic.ini`` on purpose: ``env.py`` only calls
    ``logging.config.fileConfig`` when a config file is set, and that
    would disable every logger the app has already configured. The
    database URL comes from ``env.py`` itself (``backend.app.database``).
    """
    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    return cfg


def upgrade_to_head() -> None:
    """Apply every pending migration. Blocking -- run it off the event loop."""
    command.upgrade(alembic_config(), "head")
