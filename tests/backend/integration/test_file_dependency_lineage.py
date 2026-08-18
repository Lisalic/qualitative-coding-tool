"""Integration coverage for `async_link_file_to_project`
(backend/app/database.py), which builds its INSERT via
`sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing(...)`.
That construct only compiles against the postgresql dialect -- it's the
one piece of this codebase's ORM layer that unit tests genuinely cannot
exercise against SQLite (confirmed while writing
tests/backend/routes/test_project_routes.py, which had to insert into
`project_files_table` directly instead).
"""

from sqlalchemy import select

from backend.app.database import (
    File,
    Project,
    User,
    async_link_file_to_project,
    project_files_table,
)


async def test_link_file_to_project_creates_association_row(integration_async_session):
    session = integration_async_session
    user = User(email="lineage@x.com", password="hash")
    session.add(user)
    await session.flush()

    proj = Project(user_id=user.id, projectname="P1")
    file = File(user_id=user.id, filename="f1", schemaname="proj_lineage_a", file_type="raw_data")
    session.add_all([proj, file])
    await session.flush()

    await async_link_file_to_project(session, file.id, proj.id)
    await session.commit()

    result = await session.execute(
        select(project_files_table).where(
            project_files_table.c.project_id == proj.id,
            project_files_table.c.file_id == file.id,
        )
    )
    assert result.first() is not None


async def test_link_file_to_project_on_conflict_do_nothing_is_idempotent(
    integration_async_session,
):
    """The whole point of `on_conflict_do_nothing`: linking the same
    file+project pair twice must not raise a duplicate-key error.
    """
    session = integration_async_session
    user = User(email="lineage2@x.com", password="hash")
    session.add(user)
    await session.flush()

    proj = Project(user_id=user.id, projectname="P1")
    file = File(user_id=user.id, filename="f1", schemaname="proj_lineage_b", file_type="raw_data")
    session.add_all([proj, file])
    await session.flush()

    await async_link_file_to_project(session, file.id, proj.id)
    await async_link_file_to_project(session, file.id, proj.id)  # duplicate, must not raise
    await session.commit()

    result = await session.execute(
        select(project_files_table).where(
            project_files_table.c.project_id == proj.id,
            project_files_table.c.file_id == file.id,
        )
    )
    rows = result.fetchall()
    assert len(rows) == 1  # not duplicated
