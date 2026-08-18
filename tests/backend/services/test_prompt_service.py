"""Unit tests for backend/app/services/prompt_service.py.

Runs directly against an in-memory async SQLite session (the
``async_sqlite_engine`` fixture from ``tests/conftest.py``), bypassing the
HTTP layer entirely -- ``tests/backend/routes/test_prompt_routes.py``
covers the route/auth/response-shape behavior on top of this.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import User
from backend.app.services import prompt_service


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session, email: str = "a@b.com") -> User:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    return user


class TestListPrompts:
    async def test_empty_list(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            rows = await prompt_service.list_prompts(session, user.id)
            assert rows == []

    async def test_lists_only_own_prompts(self, session_factory) -> None:
        async with session_factory() as session:
            u1 = await _make_user(session, "u1@x.com")
            u2 = await _make_user(session, "u2@x.com")
            await prompt_service.create_prompt(session, u1.id, "p1", "text1", "filter")
            await prompt_service.create_prompt(session, u2.id, "p2", "text2", "filter")

            rows = await prompt_service.list_prompts(session, u1.id)
            assert [r.promptname for r in rows] == ["p1"]

    async def test_filters_by_type(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await prompt_service.create_prompt(session, user.id, "a", "text", "filter")
            await prompt_service.create_prompt(session, user.id, "b", "text", "generate")

            rows = await prompt_service.list_prompts(session, user.id, prompt_type="generate")
            assert [r.promptname for r in rows] == ["b"]


class TestCreatePrompt:
    async def test_create(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            created = await prompt_service.create_prompt(
                session, user.id, "p1", "some text", "filter"
            )
            assert created.id is not None
            assert created.user_id == user.id
            assert created.promptname == "p1"
            assert created.prompt == "some text"
            assert created.type == "filter"


class TestUpdatePrompt:
    async def test_update_happy_path(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            created = await prompt_service.create_prompt(
                session, user.id, "orig", "orig text", "filter"
            )

            updated = await prompt_service.update_prompt(
                session, user.id, created.id, promptname="renamed"
            )
            assert updated.promptname == "renamed"
            assert updated.prompt == "orig text"  # untouched field preserved
            assert updated.type == "filter"

    async def test_update_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await prompt_service.update_prompt(session, user.id, 999999, promptname="x")

    async def test_update_wrong_owner(self, session_factory) -> None:
        async with session_factory() as session:
            u1 = await _make_user(session, "u1@x.com")
            u2 = await _make_user(session, "u2@x.com")
            created = await prompt_service.create_prompt(
                session, u1.id, "orig", "orig text", "filter"
            )
            with pytest.raises(ForbiddenError):
                await prompt_service.update_prompt(
                    session, u2.id, created.id, promptname="hijacked"
                )


class TestDeletePrompt:
    async def test_delete_happy_path(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            created = await prompt_service.create_prompt(
                session, user.id, "p1", "text", "filter"
            )
            await prompt_service.delete_prompt(session, user.id, created.id)

            rows = await prompt_service.list_prompts(session, user.id)
            assert rows == []

    async def test_delete_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await prompt_service.delete_prompt(session, user.id, 999999)

    async def test_delete_wrong_owner(self, session_factory) -> None:
        async with session_factory() as session:
            u1 = await _make_user(session, "u1@x.com")
            u2 = await _make_user(session, "u2@x.com")
            created = await prompt_service.create_prompt(
                session, u1.id, "p1", "text", "filter"
            )
            with pytest.raises(ForbiddenError):
                await prompt_service.delete_prompt(session, u2.id, created.id)
