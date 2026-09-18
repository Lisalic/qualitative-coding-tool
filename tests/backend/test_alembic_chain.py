"""Static checks on the Alembic revision chain itself.

Needs no database -- ``ScriptDirectory`` only reads the revision files
under ``backend/alembic/versions/``. Kept separate from
``tests/backend/integration/test_alembic_migration.py`` (which actually
runs ``upgrade``/``downgrade`` against a live Postgres and is opt-in)
so this fast, always-on check catches an accidental second head or a
down-revision repoint without needing a database at all.
"""

from __future__ import annotations

import os

from alembic.config import Config
from alembic.script import ScriptDirectory

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _script_directory() -> ScriptDirectory:
    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(REPO_ROOT, "backend", "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_exactly_one_head() -> None:
    """A second head means a merge revision is missing -- `alembic
    upgrade head` would refuse to run at all against a real database.
    """
    heads = _script_directory().get_heads()
    assert len(heads) == 1, f"expected exactly one Alembic head, found {heads!r}"


def test_chain_is_a_single_unbroken_line_to_base() -> None:
    """Every revision has exactly one down_revision (or None at the
    base), walking from head to base with no branch point and no gap.
    """
    script = _script_directory()
    seen: set[str] = set()
    revision = script.get_current_head()
    assert revision is not None, "no head revision found at all"

    while revision is not None:
        assert revision not in seen, f"cycle detected in revision chain at {revision!r}"
        seen.add(revision)
        rev = script.get_revision(revision)
        down = rev.down_revision
        assert not isinstance(down, (list, tuple)), (
            f"revision {revision!r} has multiple down_revisions {down!r} -- "
            "that's a merge point, not a single unbroken chain"
        )
        revision = down

    # Every revision file on disk must appear in that walk -- otherwise
    # something is orphaned (unreachable from head) or there's a second
    # chain entirely.
    all_revisions = {r.revision for r in script.walk_revisions()}
    assert seen == all_revisions, (
        f"revisions unreachable from head: {all_revisions - seen!r}"
    )
