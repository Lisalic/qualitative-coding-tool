"""Integration coverage proving `file_service.move_rows`' new set-based
copy (`raw_data_repo.copy_rows_by_id`) lands the same row content, against
a real Postgres, as a naive per-row `SELECT`+`INSERT` copy would.

Runs against real Postgres (not SQLite) specifically to exercise the
actual `INSERT ... SELECT ...` set-based statement
`raw_data_repo.copy_rows_by_id` builds, matching how the endpoint
behaves in production -- `tests/backend/services/test_file_service.py`
already covers the same behavior against SQLite for fast unit-level
regression, this is the real-engine confirmation the plan asks for.

Source-side deletion semantics are deliberately NOT compared against the
old per-row loop's hard `DELETE` any more: `move_rows` now closes the
source's copy (SCD-2 `valid_to`) instead of deleting it -- see
`file_service.move_rows`'s docstring -- so this file separately asserts
the new soft-close behavior against its own copy of the source data
(`src`), keeping the "content lands correctly" comparison against an
independent, untouched baseline copy (`src_baseline`) rather than
reusing one source file across both phases (which would otherwise hit
the exact identity-map/surrogate-PK footguns a real ORM session has
when two phases of a test both touch the same in-memory row objects --
not a production hazard, since real request handlers use a fresh
session per request).
"""

from sqlalchemy import select

from backend.app.database import File, User
from backend.app.services import file_service
from backend.app.storage_models import Comment, Submission


async def _naive_copy(session, *, source_file_id, target_file_id, table, row_ids):
    """The simplest possible per-row `SELECT`+`INSERT` copy, as the
    "known-good" content baseline `copy_rows_by_id`'s set-based
    `INSERT ... SELECT` is compared against. Never deletes from the
    source -- this function is about content parity only.
    """
    model = Submission if table == "submissions" else Comment
    result = await session.execute(select(model).where(model.file_id == source_file_id, model.id.in_(row_ids)))
    rows = result.scalars().all()
    for row in rows:
        data = {
            c.name: getattr(row, c.name)
            for c in model.__table__.c
            if c.name not in ("pk", "file_id", "valid_from", "valid_to")
        }
        session.add(model(file_id=target_file_id, valid_from=1, valid_to=None, **data))
    await session.commit()
    return len(rows)


async def test_move_rows_matches_naive_per_row_copy_for_submissions(integration_async_session):
    session = integration_async_session
    user = User(email="parity1@x.com", password="hash")
    session.add(user)
    await session.flush()

    src = File(user_id=user.id, filename="src", schemaname="proj_parity_src1", file_type="raw_data")
    src_baseline = File(user_id=user.id, filename="src_baseline", schemaname="proj_parity_src1b", file_type="raw_data")
    tgt_new = File(user_id=user.id, filename="tgt_new", schemaname="proj_parity_tgt_new", file_type="raw_data")
    tgt_baseline = File(user_id=user.id, filename="tgt_baseline", schemaname="proj_parity_tgt_baseline", file_type="raw_data")
    session.add_all([src, src_baseline, tgt_new, tgt_baseline])
    await session.flush()

    def _rows_for(file_id):
        return [
            Submission(
                file_id=file_id, id=f"s{i}", subreddit="sub", title=f"title {i}",
                selftext=f"body text number {i}", author="author", created_utc=1000 + i,
                score=i, num_comments=0, word_count=3,
            )
            for i in range(5)
        ]

    session.add_all(_rows_for(src.id) + _rows_for(src_baseline.id))
    await session.commit()

    move_ids = ["s1", "s3", "s4"]

    # New set-based path, via the actual service function under test.
    moved_new = await file_service.move_rows(
        session, user.id,
        source_schema="proj_parity_src1", target_schema="proj_parity_tgt_new",
        table="submissions", row_ids=move_ids,
    )

    # Independent naive baseline, run against the untouched `src_baseline`
    # copy -- content-only comparison, no shared session-identity state
    # with the rows `move_rows` already flushed above.
    moved_baseline = await _naive_copy(
        session, source_file_id=src_baseline.id, target_file_id=tgt_baseline.id,
        table="submissions", row_ids=move_ids,
    )

    assert moved_new == moved_baseline == 3

    new_rows = (await session.execute(select(Submission).where(Submission.file_id == tgt_new.id))).scalars().all()
    baseline_rows = (
        await session.execute(select(Submission).where(Submission.file_id == tgt_baseline.id))
    ).scalars().all()

    def _content(rs):
        return sorted(
            (r.id, r.subreddit, r.title, r.selftext, r.author, r.created_utc, r.score, r.num_comments)
            for r in rs
        )

    assert _content(new_rows) == _content(baseline_rows)

    # `move_rows` closes the source's copy (SCD-2) rather than deleting
    # it: the moved rows are still IN the table, just no longer LIVE.
    live_in_src = (
        await session.execute(select(Submission.id).where(Submission.file_id == src.id, Submission.valid_to.is_(None)))
    ).scalars().all()
    assert sorted(live_in_src) == ["s0", "s2"]
    all_in_src = (await session.execute(select(Submission.id).where(Submission.file_id == src.id))).scalars().all()
    assert sorted(all_in_src) == ["s0", "s1", "s2", "s3", "s4"]
