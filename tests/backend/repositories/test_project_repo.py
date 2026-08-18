import pytest

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import Project
from backend.app.repositories.project_repo import get_owned_project

from .conftest import make_user


class TestGetOwnedProject:
    async def test_returns_owned_project(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            proj = Project(user_id=user.id, projectname="P1")
            session.add(proj)
            await session.commit()

            found = await get_owned_project(session, proj.id, user.id)
            assert found.id == proj.id
            assert found.projectname == "P1"

    async def test_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            with pytest.raises(NotFoundError):
                await get_owned_project(session, 999999, user.id)

    async def test_wrong_owner_raises_forbidden(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await make_user(session, "owner@x.com")
            other = await make_user(session, "other@x.com")

            proj = Project(user_id=owner.id, projectname="P1")
            session.add(proj)
            await session.commit()

            with pytest.raises(ForbiddenError):
                await get_owned_project(session, proj.id, other.id)
