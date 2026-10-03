"""Selections larger than Postgres's bind-parameter limit.

asyncpg refuses a statement with more than 32,767 parameters, and
``column.in_(ids)`` binds one per id, so saving a filter that kept 35,000
posts failed outright. ``core/sql_filters.py::in_values`` and
``data_service._exclude_clause`` now bind the whole list as one array
parameter on Postgres. SQLite has no such limit, so only this suite can
see the difference.
"""

from sqlalchemy import func, select

from backend.app.database import File, Project, User
from backend.app.repositories import raw_data_repo
from backend.app.services import data_service, file_service
from backend.app.storage_models import Submission

_ROWS = 40_000


async def _large_raw_file(session) -> tuple[int, int, File]:
    user = User(email="large-selection@x.com", password="hash")
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, projectname="large")
    raw = File(user_id=user.id, filename="raw", schemaname="proj_large_raw", file_type="raw_data")
    session.add_all([project, raw])
    await session.flush()
    await raw_data_repo.bulk_insert_submissions(
        session, raw.id, [{"id": f"p{i}", "title": "t", "selftext": "some body text"} for i in range(_ROWS)]
    )
    await session.commit()
    return user.id, project.id, raw


async def _live_count(session, file_id: int) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(Submission).where(
                Submission.file_id == file_id, Submission.valid_to.is_(None)
            )
        )
    ).scalar_one()


async def test_selections_beyond_the_parameter_limit(integration_async_session) -> None:
    session = integration_async_session
    user_id, project_id, raw = await _large_raw_file(session)

    filtered, _ = await data_service.create_manual_filtered_data(
        session, user_id, database=raw.schemaname, name="kept", description=None,
        project_id=project_id, post_ids=[f"p{i}" for i in range(35_000)], comment_ids=[],
    )
    assert await _live_count(session, filtered.id) == 35_000

    deleted = await file_service.delete_rows(
        session, user_id, schemaname=filtered.schemaname, table="submissions",
        row_ids=[f"p{i}" for i in range(33_000)],
    )
    assert deleted == 33_000
    assert await _live_count(session, filtered.id) == 2_000

    # The AI preview never re-proposes rows already ruled on; a researcher
    # can have ruled on more rows than the parameter limit allows.
    sub_rows, _, _, _ = await data_service._sample_source_rows(
        session, source_file_id=raw.id, min_words=0, sub_tag_sql="", sub_tag_bind={},
        com_tag_sql="", com_tag_bind={}, pct=100, use_ai_posts=False, use_ai_comments=False,
        include_comments=False, exclude_submission_ids=[f"p{i}" for i in range(_ROWS - 10)],
    )
    assert sorted(row.id for row in sub_rows) == sorted(f"p{i}" for i in range(_ROWS - 10, _ROWS))
