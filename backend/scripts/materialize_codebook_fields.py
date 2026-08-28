"""Fill ``codebook_codes`` structured columns from ``body``.

One-shot, re-runnable: a row that already has any of definition /
inclusion / exclusion / keywords / example is skipped. Unlabeled leftover
prose becomes ``definition``. Uses the same splitter as markdown import
(``core/codebook_render.materialize_fields_from_body``).

Usage (from repo root):

    .venv/bin/python -m backend.scripts.materialize_codebook_fields --dry-run
    .venv/bin/python -m backend.scripts.materialize_codebook_fields
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from backend.app.core.codebook_render import materialize_fields_from_body
from backend.app.database import SessionLocal
from backend.app.jobs import models as job_models  # noqa: F401 -- registers jobs for ArtifactVersion FKs
from backend.app.versioning_models import CodebookCode


def _needs_materialize(row: CodebookCode) -> bool:
    return bool((row.body or "").strip())


def run(*, dry_run: bool) -> int:
    updated = 0
    skipped = 0
    with SessionLocal() as session:
        rows = session.scalars(select(CodebookCode)).all()
        for row in rows:
            if not _needs_materialize(row):
                skipped += 1
                continue
            fields = materialize_fields_from_body(row.body)
            changed = (
                row.definition != fields["definition"]
                or row.inclusion != fields["inclusion"]
                or row.exclusion != fields["exclusion"]
                or row.keywords != fields["keywords"]
                or row.example != fields["example"]
                or row.body != (fields["body"] or "")
            )
            row.definition = fields["definition"]
            row.inclusion = fields["inclusion"]
            row.exclusion = fields["exclusion"]
            row.keywords = fields["keywords"]
            row.example = fields["example"]
            row.body = fields["body"] or ""
            if changed:
                updated += 1
            else:
                skipped += 1
        if dry_run:
            session.rollback()
        else:
            session.commit()
    print(f"codebook_codes updated: {updated}")
    print(f"skipped (already structured or empty): {skipped}")
    if dry_run:
        print("dry-run: no changes committed")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
