from backend.app.database import File
from backend.app.repositories.artifact_content_repo import read_content, write_content

from .conftest import make_user


async def _make_file(session, user, schemaname: str = "sum_a") -> File:
    f = File(user_id=user.id, filename=f"{schemaname}.txt", schemaname=schemaname, file_type="summary")
    session.add(f)
    await session.commit()
    return f


class TestWriteAndReadContent:
    async def test_write_then_read_round_trips(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            await write_content(session, f.id, "hello world")
            await session.commit()

            content = await read_content(session, f.id)
            assert content == "hello world"

    async def test_write_overwrites_existing_row(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            await write_content(session, f.id, "first")
            await session.commit()

            await write_content(session, f.id, "second")
            await session.commit()

            content = await read_content(session, f.id)
            assert content == "second"

    async def test_read_missing_returns_none(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            content = await read_content(session, f.id)
            assert content is None
