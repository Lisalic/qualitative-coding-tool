"""One-time (re-runnable, per-file-type-scoped) backfill script.

Copies artifact data OUT of the old per-artifact dynamic Postgres schemas
(``files.schemaname``, e.g. ``proj_a1b2c3``/``cmp_a1b2c3``/``sum_a1b2c3``)
and INTO the new fixed tables keyed by ``file_id`` defined in
``backend/app/storage_models.py``. Purely additive: nothing in the old
dynamic schemas is read-write, modified, or dropped here -- that's a
later, separate, explicitly irreversible cleanup stage.

Run scoped to one or more file types (a later stage runs this immediately
before that stage's route code goes live), or with no ``--file-type`` at
all to cover every type:

    .venv/bin/python -m backend.scripts.migrate_to_fixed_tables --file-type raw_data
    .venv/bin/python -m backend.scripts.migrate_to_fixed_tables --file-type codebook --file-type summary
    .venv/bin/python -m backend.scripts.migrate_to_fixed_tables

Idempotent: safe to re-run. Before writing a fixed table's rows for a
given ``file_id``, the corresponding fixed table is checked for existing
rows for that ``file_id`` and skipped if already populated.

This is an offline batch CLI, not a request-serving path, so it uses the
sync engine/``SessionLocal`` (``backend/app/database.py``) rather than the
async engine -- synchronous blocking DB calls are fine and simpler here.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import insert, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from backend.app.database import File, SessionLocal, engine
from backend.app.storage_models import ArtifactContent, CodingEntry, Comment, Submission
from backend.scripts.codebook_apply import _extract_structured_records, _format_evidence_segments

logger = logging.getLogger(__name__)

# File types whose old schema holds a `submissions`/`comments` pair.
RAW_TABLE_FILE_TYPES = ("raw_data", "filtered_data")
# File types whose old schema holds a single-row `content_store` table.
CONTENT_ONLY_FILE_TYPES = ("codebook", "codebook_comparison", "summary", "coding_comparison")
# `coding` gets both a content_store blob AND a structured re-parse into
# coding_entries -- handled separately from the two groups above.
CODING_FILE_TYPE = "coding"

ALL_FILE_TYPES = (*RAW_TABLE_FILE_TYPES, *CONTENT_ONLY_FILE_TYPES, CODING_FILE_TYPE)


# ---------------------------------------------------------------------------
# word_count -- matches the Postgres `GENERATED ALWAYS AS (...)` expression
# the old per-artifact schema DDL used (normalize whitespace, split on
# spaces, count non-empty tokens; 0 for empty/`None`).
# ---------------------------------------------------------------------------


def _word_count(value: str | None) -> int:
    if not value:
        return 0
    return len(value.split())


# ---------------------------------------------------------------------------
# Reading FROM the old dynamic per-artifact schema (raw SQL, read-only).
# This is one of the few places raw dynamic-schema SQL is still correct to
# use, since we're reading from the old schema-per-artifact model, not
# writing to it.
# ---------------------------------------------------------------------------


def _table_exists(conn: Connection, schemaname: str, table: str) -> bool:
    result = conn.execute(
        text("SELECT to_regclass(:tbl)"),
        {"tbl": f'"{schemaname}"."{table}"'},
    )
    return result.scalar() is not None


def _existing_columns(conn: Connection, schemaname: str, table: str) -> set[str]:
    result = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schemaname, "table": table},
    )
    return {row[0] for row in result}


def _fetch_submissions(conn: Connection, schemaname: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, schemaname, "submissions"):
        return []
    wanted = ["id", "subreddit", "title", "selftext", "author", "created_utc", "score", "num_comments"]
    # Some older per-upload schemas predate a column being added to the
    # DDL (e.g. `subreddit`) -- select only columns that actually exist in
    # this particular schema; the fixed Submission table's other columns
    # are nullable, so a missing source column just becomes None below,
    # rather than the whole file failing to migrate at all.
    present = _existing_columns(conn, schemaname, "submissions")
    cols = [c for c in wanted if c in present]
    result = conn.execute(text(f'SELECT {", ".join(cols)} FROM "{schemaname}"."submissions"'))
    rows = [dict(row) for row in result.mappings().all()]
    missing = [c for c in wanted if c not in present]
    for row in rows:
        for c in missing:
            row[c] = None
    return rows


def _fetch_comments(conn: Connection, schemaname: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, schemaname, "comments"):
        return []
    wanted = ["id", "subreddit", "body", "author", "created_utc", "score", "link_id", "parent_id"]
    present = _existing_columns(conn, schemaname, "comments")
    cols = [c for c in wanted if c in present]
    result = conn.execute(text(f'SELECT {", ".join(cols)} FROM "{schemaname}"."comments"'))
    rows = [dict(row) for row in result.mappings().all()]
    missing = [c for c in wanted if c not in present]
    for row in rows:
        for c in missing:
            row[c] = None
    return rows


def _fetch_content_text(conn: Connection, schemaname: str) -> str | None:
    if not _table_exists(conn, schemaname, "content_store"):
        return None
    result = conn.execute(
        text(f'SELECT file_text FROM "{schemaname}"."content_store" LIMIT 1')
    )
    return result.scalar()


# ---------------------------------------------------------------------------
# Parsing the stored classification-output text into structured
# (post_id, code, evidence) rows for `coding_entries`. Reuses the parser
# `backend/scripts/codebook_apply.py` already has (the stored text is
# already in the canonical POST_ID:/CODE:/EVIDENCE: format produced by
# `normalize_coding_output`, which itself round-trips through
# `_extract_structured_records`).
# ---------------------------------------------------------------------------


def _parse_coding_entries(raw_text: str) -> list[dict[str, str]]:
    records = _extract_structured_records(raw_text)
    merged: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for post_id, entries in records:
        for code_name, evidence_segments in entries:
            key = (post_id, code_name)
            if key not in merged:
                merged[key] = []
                order.append(key)
            merged[key].extend(evidence_segments)
    return [
        {
            "post_id": post_id,
            "code": code_name,
            "evidence": _format_evidence_segments(merged[(post_id, code_name)]),
        }
        for post_id, code_name in order
    ]


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def _already_migrated(session: Session, model: type, file_id: int) -> bool:
    return session.query(model.file_id).filter(model.file_id == file_id).first() is not None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class FileError:
    file_id: int
    schemaname: str
    filename: str
    error: str


@dataclass
class MigrationReport:
    file_type: str
    files_processed: int = 0
    files_migrated: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    rows_copied: dict[str, int] = field(
        default_factory=lambda: {
            "submissions": 0,
            "comments": 0,
            "artifact_content": 0,
            "coding_entries": 0,
        }
    )
    errors: list[FileError] = field(default_factory=list)

    def format(self) -> str:
        lines = [
            f"file_type={self.file_type}: "
            f"processed={self.files_processed} migrated={self.files_migrated} "
            f"skipped={self.files_skipped} errored={self.files_errored}"
        ]
        row_bits = ", ".join(f"{k}={v}" for k, v in self.rows_copied.items() if v)
        if row_bits:
            lines.append(f"  rows copied: {row_bits}")
        for err in self.errors:
            lines.append(
                f"  ERROR file_id={err.file_id} schema={err.schemaname!r} "
                f"filename={err.filename!r}: {err.error}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-file migration, one file_type category at a time
# ---------------------------------------------------------------------------


def _migrate_raw_table_file(session: Session, file: File, report: MigrationReport) -> None:
    have_submissions = _already_migrated(session, Submission, file.id)
    have_comments = _already_migrated(session, Comment, file.id)
    if have_submissions and have_comments:
        logger.info("file_id=%s (%s) already migrated, skipping", file.id, file.schemaname)
        report.files_skipped += 1
        return

    with engine.connect() as conn:
        submissions = [] if have_submissions else _fetch_submissions(conn, file.schemaname)
        comments = [] if have_comments else _fetch_comments(conn, file.schemaname)

    if submissions:
        payload = []
        for row in submissions:
            title = row.get("title") or ""
            selftext = row.get("selftext") or ""
            payload.append(
                {
                    **row,
                    "file_id": file.id,
                    "word_count": _word_count(f"{title} {selftext}".strip()),
                }
            )
        session.execute(insert(Submission), payload)
        report.rows_copied["submissions"] += len(payload)

    if comments:
        payload = []
        for row in comments:
            payload.append(
                {
                    **row,
                    "file_id": file.id,
                    "word_count": _word_count(row.get("body") or ""),
                }
            )
        session.execute(insert(Comment), payload)
        report.rows_copied["comments"] += len(payload)

    report.files_migrated += 1


def _migrate_content_file(session: Session, file: File, report: MigrationReport) -> None:
    if _already_migrated(session, ArtifactContent, file.id):
        logger.info("file_id=%s (%s) already migrated, skipping", file.id, file.schemaname)
        report.files_skipped += 1
        return

    with engine.connect() as conn:
        content = _fetch_content_text(conn, file.schemaname)

    if content is None:
        raise ValueError(f"No content_store text found in schema {file.schemaname!r}")

    session.execute(insert(ArtifactContent), [{"file_id": file.id, "content": content}])
    report.rows_copied["artifact_content"] += 1
    report.files_migrated += 1


def _migrate_coding_file(session: Session, file: File, report: MigrationReport) -> None:
    have_content = _already_migrated(session, ArtifactContent, file.id)
    have_entries = _already_migrated(session, CodingEntry, file.id)
    if have_content and have_entries:
        logger.info("file_id=%s (%s) already migrated, skipping", file.id, file.schemaname)
        report.files_skipped += 1
        return

    with engine.connect() as conn:
        content = _fetch_content_text(conn, file.schemaname)

    if content is None:
        raise ValueError(f"No content_store text found in schema {file.schemaname!r}")

    if not have_content:
        session.execute(insert(ArtifactContent), [{"file_id": file.id, "content": content}])
        report.rows_copied["artifact_content"] += 1

    if not have_entries:
        try:
            entries = _parse_coding_entries(content)
        except Exception as exc:  # noqa: BLE001 - log and continue, don't abort the run
            logger.error(
                "file_id=%s (%s): failed to parse coding output, skipping coding_entries: %s",
                file.id,
                file.schemaname,
                exc,
            )
            report.errors.append(
                FileError(file.id, file.schemaname, file.filename, f"coding-output parse failed: {exc}")
            )
            entries = []
        if entries:
            payload = [{"file_id": file.id, **entry} for entry in entries]
            session.execute(insert(CodingEntry), payload)
            report.rows_copied["coding_entries"] += len(payload)

    report.files_migrated += 1


def _migrate_one_file(session: Session, file: File, report: MigrationReport) -> None:
    try:
        if file.file_type in RAW_TABLE_FILE_TYPES:
            _migrate_raw_table_file(session, file, report)
        elif file.file_type in CONTENT_ONLY_FILE_TYPES:
            _migrate_content_file(session, file, report)
        elif file.file_type == CODING_FILE_TYPE:
            _migrate_coding_file(session, file, report)
        else:
            raise ValueError(f"Unsupported file_type: {file.file_type!r}")
        session.commit()
    except Exception as exc:  # noqa: BLE001 - one bad file must not abort the whole run
        session.rollback()
        logger.error(
            "file_id=%s (%s) failed to migrate: %s", file.id, file.schemaname, exc
        )
        report.files_errored += 1
        report.errors.append(FileError(file.id, file.schemaname, file.filename, str(exc)))


def migrate_file_type(session: Session, file_type: str) -> MigrationReport:
    """Migrate every ``File`` row with ``file_type`` from its old dynamic
    schema into the new fixed tables. Each file's migration runs in its
    own transaction (committed/rolled back independently), so one file's
    failure never rolls back another file's already-migrated data.
    """
    report = MigrationReport(file_type=file_type)
    files = session.query(File).filter(File.file_type == file_type).order_by(File.id).all()
    for file in files:
        report.files_processed += 1
        _migrate_one_file(session, file, report)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def migrate(file_types: list[str] | None = None) -> list[MigrationReport]:
    types = file_types if file_types else list(ALL_FILE_TYPES)
    session = SessionLocal()
    try:
        return [migrate_file_type(session, file_type) for file_type in types]
    finally:
        session.close()


def format_reports(reports: list[MigrationReport]) -> str:
    return "\n\n".join(report.format() for report in reports)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate_to_fixed_tables",
        description=(
            "Backfill: copy artifact data from the old per-artifact dynamic "
            "Postgres schemas (files.schemaname) into the new fixed tables in "
            "backend/app/storage_models.py. Additive and idempotent -- never "
            "modifies or drops the old schemas."
        ),
    )
    parser.add_argument(
        "--file-type",
        action="append",
        dest="file_types",
        choices=sorted(ALL_FILE_TYPES),
        help="File type to migrate. Repeatable. Omit to migrate every type.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    reports = migrate(args.file_types)
    print(format_reports(reports))
    return 1 if any(report.files_errored for report in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
