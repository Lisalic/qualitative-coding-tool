"""Drop old per-artifact dynamic Postgres schemas (``proj_*``/``cmp_*``/
``sum_*``) for files already confirmed migrated to the fixed storage
tables (``backend/scripts/migrate_to_fixed_tables.py``).

This is the one genuinely irreversible step in the backend storage-model
refactor -- everything up to this point (landing the fixed tables,
backfilling them, cutting routes over) leaves the old schemas untouched
as a rollback fallback. This script removes that fallback for whichever
schemas it's told to drop, so it defaults to a dry run and only a real
``DROP SCHEMA`` is issued with ``--confirm``.

Only ever considers a schema droppable if:
  1. it has a matching ``files.schemaname`` row, AND
  2. that file's data is confirmed present in the fixed table(s) for its
     file_type (the same check ``migrate_to_fixed_tables.py`` uses to
     decide "already migrated").

Schemas with no matching ``files`` row at all (orphaned -- unreachable
by the app through any code path, old or new) are deliberately NOT
considered here; that is a separate, less-understood category left for
a human to look at directly, not something this script touches.

Usage:
    .venv/bin/python -m backend.scripts.drop_migrated_schemas              # dry run, prints the plan
    .venv/bin/python -m backend.scripts.drop_migrated_schemas --confirm    # actually drops them

This is an offline batch CLI, not a request-serving path -- uses the
sync engine/``SessionLocal`` like ``migrate_to_fixed_tables.py``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field

from sqlalchemy import text

from backend.app.database import File, SessionLocal, engine
from backend.app.storage_models import ArtifactContent, CodingEntry, Comment, Submission
from backend.scripts.migrate_to_fixed_tables import (
    CODING_FILE_TYPE,
    CONTENT_ONLY_FILE_TYPES,
    RAW_TABLE_FILE_TYPES,
    _already_migrated,
)

logger = logging.getLogger(__name__)


@dataclass
class DropCandidate:
    file_id: int
    schemaname: str
    filename: str
    file_type: str


@dataclass
class DropResult:
    dropped: list[DropCandidate] = field(default_factory=list)
    skipped_not_confirmed_migrated: list[DropCandidate] = field(default_factory=list)
    errors: list[tuple[DropCandidate, str]] = field(default_factory=list)

    def format(self) -> str:
        lines = [
            f"Dropped: {len(self.dropped)}, "
            f"skipped (not confirmed migrated): {len(self.skipped_not_confirmed_migrated)}, "
            f"errors: {len(self.errors)}"
        ]
        for c in self.dropped:
            lines.append(f"  DROPPED  file_id={c.file_id} schema={c.schemaname!r} type={c.file_type}")
        for c in self.skipped_not_confirmed_migrated:
            lines.append(
                f"  SKIPPED  file_id={c.file_id} schema={c.schemaname!r} type={c.file_type} "
                "(not confirmed migrated -- left in place)"
            )
        for c, err in self.errors:
            lines.append(f"  ERROR    file_id={c.file_id} schema={c.schemaname!r}: {err}")
        return "\n".join(lines)


def _is_confirmed_migrated(session, file: File) -> bool:
    """Same "already migrated" check migrate_to_fixed_tables.py uses to
    decide whether to skip re-copying a file -- here it's the gate for
    whether a schema is safe to drop at all.
    """
    if file.file_type in RAW_TABLE_FILE_TYPES:
        # A raw/filtered-data file might legitimately have zero rows in
        # one or both tables (e.g. an empty filter result) -- so being
        # "migrated" here means: for whichever of submissions/comments
        # actually has rows in the OLD schema, the fixed table has rows
        # too; if the old schema has nothing in either table, there's
        # nothing to lose either way and the schema is still droppable.
        with engine.connect() as conn:
            old_subs = conn.execute(
                text("SELECT to_regclass(:tbl)"), {"tbl": f'"{file.schemaname}"."submissions"'}
            ).scalar()
            old_subs_count = (
                conn.execute(text(f'SELECT COUNT(*) FROM "{file.schemaname}"."submissions"')).scalar()
                if old_subs
                else 0
            )
            old_comm = conn.execute(
                text("SELECT to_regclass(:tbl)"), {"tbl": f'"{file.schemaname}"."comments"'}
            ).scalar()
            old_comm_count = (
                conn.execute(text(f'SELECT COUNT(*) FROM "{file.schemaname}"."comments"')).scalar()
                if old_comm
                else 0
            )
        if old_subs_count and not _already_migrated(session, Submission, file.id):
            return False
        if old_comm_count and not _already_migrated(session, Comment, file.id):
            return False
        return True

    if file.file_type in CONTENT_ONLY_FILE_TYPES:
        return _already_migrated(session, ArtifactContent, file.id)

    if file.file_type == CODING_FILE_TYPE:
        return _already_migrated(session, ArtifactContent, file.id)

    # Unknown file_type for this script's purposes -- do not touch it.
    return False


def find_droppable_schemas(session) -> tuple[list[DropCandidate], list[DropCandidate]]:
    """Returns (droppable, not_confirmed_migrated) -- both scoped to
    files whose schemaname currently exists as a real Postgres schema.
    """
    with engine.connect() as conn:
        existing_schemas = {
            row[0]
            for row in conn.execute(
                text("SELECT nspname FROM pg_namespace WHERE nspname ~ '^(proj_|cmp_|sum_)'")
            )
        }

    files = session.query(File).filter(File.schemaname.in_(existing_schemas)).all()

    droppable: list[DropCandidate] = []
    not_confirmed: list[DropCandidate] = []
    for file in files:
        candidate = DropCandidate(
            file_id=file.id, schemaname=file.schemaname, filename=file.filename, file_type=file.file_type
        )
        if _is_confirmed_migrated(session, file):
            droppable.append(candidate)
        else:
            not_confirmed.append(candidate)
    return droppable, not_confirmed


def drop_schemas(candidates: list[DropCandidate], *, confirm: bool) -> DropResult:
    result = DropResult()
    for candidate in candidates:
        if not confirm:
            result.dropped.append(candidate)  # dry-run: report what WOULD be dropped
            continue
        try:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{candidate.schemaname}" CASCADE'))
            logger.info("Dropped schema %s (file_id=%s)", candidate.schemaname, candidate.file_id)
            result.dropped.append(candidate)
        except Exception as exc:  # noqa: BLE001 - one bad schema shouldn't abort the batch
            logger.error("Failed to drop schema %s: %s", candidate.schemaname, exc)
            result.errors.append((candidate, str(exc)))
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually execute DROP SCHEMA. Without this flag, only prints the plan.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_arg_parser().parse_args(argv)

    session = SessionLocal()
    try:
        droppable, not_confirmed = find_droppable_schemas(session)
    finally:
        session.close()

    if not_confirmed:
        print(f"NOTE: {len(not_confirmed)} schema(s) matched a files row but are NOT confirmed migrated -- left alone:")
        for c in not_confirmed:
            print(f"  file_id={c.file_id} schema={c.schemaname!r} type={c.file_type} filename={c.filename!r}")
        print()

    mode = "EXECUTING (--confirm passed)" if args.confirm else "DRY RUN (pass --confirm to actually drop)"
    print(f"{mode} -- {len(droppable)} schema(s) confirmed migrated and droppable:\n")

    result = drop_schemas(droppable, confirm=args.confirm)
    print(result.format())
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
