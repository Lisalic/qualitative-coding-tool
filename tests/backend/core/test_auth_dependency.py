from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.auth import password_fingerprint
from backend.app.core.auth_dependency import optional_user_id, require_user_id
from backend.app.core.exceptions import UnauthorizedError
from backend.app.database import User


@pytest.fixture()
async def db(async_sqlite_engine):
    async with async_sessionmaker(async_sqlite_engine, expire_on_commit=False)() as session:
        yield session


async def _user(db, password: str = "hash") -> User:
    user = User(email=f"{password}@example.com", password=password)
    db.add(user)
    await db.commit()
    return user


class TestRequireUserId:
    async def test_current_session_returns_user_id(self, fake_request, make_token, db) -> None:
        user = await _user(db)
        req = fake_request(cookies={"access_token": make_token(sub=str(user.id))})
        assert await require_user_id(req, db) == user.id

    async def test_bearer_header_also_accepted(self, fake_request, make_token, db) -> None:
        user = await _user(db)
        req = fake_request(headers={"Authorization": f"Bearer {make_token(sub=str(user.id))}"})
        assert await require_user_id(req, db) == user.id

    @pytest.mark.parametrize("cookies", [{}, {"access_token": "not-a-jwt"}], ids=["no token", "malformed"])
    async def test_no_valid_token_raises_unauthorized(self, fake_request, db, cookies) -> None:
        with pytest.raises(UnauthorizedError):
            await require_user_id(fake_request(cookies=cookies), db)

    async def test_session_from_before_a_password_change_is_rejected(self, fake_request, make_token, db) -> None:
        user = await _user(db, password="new-hash")
        old_session = make_token(sub=str(user.id), pwh=password_fingerprint("old-hash"))
        with pytest.raises(UnauthorizedError):
            await require_user_id(fake_request(cookies={"access_token": old_session}), db)

    async def test_session_without_a_password_fingerprint_is_rejected(self, fake_request, make_token, db) -> None:
        user = await _user(db)
        with pytest.raises(UnauthorizedError):
            await require_user_id(fake_request(cookies={"access_token": make_token(sub=str(user.id), pwh="")}), db)

    async def test_session_for_a_user_that_no_longer_exists_is_rejected(self, fake_request, make_token, db) -> None:
        with pytest.raises(UnauthorizedError):
            await require_user_id(fake_request(cookies={"access_token": make_token(sub="99999")}), db)

    async def test_a_failed_lookup_is_an_error_not_an_accepted_session(self, fake_request, make_token) -> None:
        """Fail closed: if the revocation check can't run, nothing is let in."""
        broken = AsyncMock()
        broken.execute.side_effect = OperationalError("SELECT", {}, Exception("connection refused"))
        with pytest.raises(OperationalError):
            await require_user_id(fake_request(cookies={"access_token": make_token(sub="1")}), broken)


class TestOptionalUserId:
    async def test_current_session_returns_user_id(self, fake_request, make_token, db) -> None:
        user = await _user(db)
        req = fake_request(cookies={"access_token": make_token(sub=str(user.id))})
        assert await optional_user_id(req, db) == user.id

    async def test_no_token_returns_none(self, fake_request, db) -> None:
        assert await optional_user_id(fake_request(), db) is None

    async def test_revoked_session_returns_none(self, fake_request, make_token, db) -> None:
        user = await _user(db, password="new-hash")
        req = fake_request(cookies={"access_token": make_token(sub=str(user.id), pwh=password_fingerprint("old"))})
        assert await optional_user_id(req, db) is None
