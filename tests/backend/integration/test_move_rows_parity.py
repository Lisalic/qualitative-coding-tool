"""Integration coverage proving `file_service.move_rows`' new set-based
copy (`raw_data_repo.copy_rows_by_id`) produces the same row/content
result, against a real Postgres, as the old per-row
`SELECT`+`INSERT`+`DELETE` Python loop it replaced in
`backend/app/api/file_routes.py`.

Runs against real Postgres (not SQLite) specifically to exercise the
actual `INSERT ... SELECT ...` set-based statement
`raw_data_repo.copy_rows_by_id` builds, matching how the endpoint
behaves in production -- `tests/backend/services/test_file_service.py`
already covers the same behavior against SQLite for fast unit-level
regression, this is the real-engine confirmation the plan asks for.
"""

from sqlalchemy import select

from backend.app.database import File, User
from backend.app.services import file_service
from backend.app.storage_models import Comment, Submission


async def _old_style_move(session, *, source_file_id, target_file_id, table, row_ids):
    """Reimplements the exact behavior of the OLD per-row loop
    (`file_routes.py::move_rows`, pre-refactor) directly against the
    fixed tables, as the "known-good" baseline to compare the new
    set-based path's result against: SELECT each row from source by id,
    INSERT it into target, then DELETE it from source.
    """
    model = Submission if table == "submissions" else Comment
    result = await session.execute(select(model).where(model.file_id == source_file_id, model.id.in_(row_ids)))
    rows = result.scalars().all()
    for row in rows:
        data = {c.name: getattr(row, c.name) for c in model.__table__.c if c.name != "file_id"}
        session.add(model(file_id=target_file_id, **data))
    await session.execute(
        model.__table__.delete().where(model.file_id == source_file_id, model.id.in_(row_ids))
    )
    await session.commit()
    return len(rows)


async def test_move_rows_matches_old_per_row_loop_for_submissions(integration_async_session):
    session = integration_async_session
    user = User(email="parity1@x.com", password="hash")
    session.add(user)
    await session.flush()

    src = File(user_id=user.id, filename="src", schemaname="proj_parity_src1", file_type="raw_data")
    tgt_new = File(user_id=user.id, filename="tgt_new", schemaname="proj_parity_tgt_new", file_type="raw_data")
    tgt_old = File(user_id=user.id, filename="tgt_old", schemaname="proj_parity_tgt_old", file_type="raw_data")
    session.add_all([src, tgt_new, tgt_old])
    await session.flush()

    rows = [
        Submission(
            file_id=src.id, id=f"s{i}", subreddit="sub", title=f"title {i}",
            selftext=f"body text number {i}", author="author", created_utc=1000 + i,
            score=i, num_comments=0, word_count=3,
        )
        for i in range(5)
    ]
    session.add_all(rows)
    await session.commit()

    move_ids = ["s1", "s3", "s4"]

    # New set-based path, via the actual service function under test.
    moved_new = await file_service.move_rows(
        session, user.id,
        source_schema="proj_parity_src1", target_schema="proj_parity_tgt_new",
        table="submissions", row_ids=move_ids,
    )

    # Re-seed an identical source for the old-style baseline (the new
    # path already deleted the moved rows out of `src`).
    session.add_all([
        Submission(
            file_id=src.id, id=f"s{i}", subreddit="sub", title=f"title {i}",
            selftext=f"body text number {i}", author="author", created_utc=1000 + i,
            score=i, num_comments=0, word_count=3,
        )
        for i in [1, 3, 4]
    ])
    await session.commit()

    moved_old = await _old_style_move(
        session, source_file_id=src.id, target_file_id=tgt_old.id, table="submissions", row_ids=move_ids,
    )

    assert moved_new == moved_old == 3

    new_rows = (await session.execute(select(Submission).where(Submission.file_id == tgt_new.id))).scalars().all()
    old_rows = (await session.execute(select(Submission).where(Submission.file_id == tgt_old.id))).scalars().all()

    def _content(rs):
        return sorted(
            (r.id, r.subreddit, r.title, r.selftext, r.author, r.created_utc, r.score, r.num_comments)
            for r in rs
        )

    assert _content(new_rows) == _content(old_rows)

    # Both source copies end up with only the two un-moved rows.
    remaining = (await session.execute(select(Submission.id).where(Submission.file_id == src.id))).scalars().all()
    assert sorted(remaining) == ["s0", "s2"]
