import pytest

from backend.app.core.auth_dependency import optional_user_id, require_user_id
from backend.app.core.exceptions import UnauthorizedError


class TestRequireUserId:
    def test_valid_token_returns_int_user_id(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub="42")})
        assert require_user_id(req) == 42

    def test_no_token_raises_unauthorized(self, fake_request) -> None:
        with pytest.raises(UnauthorizedError):
            require_user_id(fake_request())

    def test_invalid_token_raises_unauthorized(self, fake_request) -> None:
        with pytest.raises(UnauthorizedError):
            require_user_id(fake_request(cookies={"access_token": "not-a-jwt"}))

    def test_bearer_header_also_accepted(self, fake_request, make_token) -> None:
        req = fake_request(headers={"Authorization": f"Bearer {make_token(sub='7')}"})
        assert require_user_id(req) == 7


class TestOptionalUserId:
    def test_valid_token_returns_int(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub="5")})
        assert optional_user_id(req) == 5

    def test_no_token_returns_none(self, fake_request) -> None:
        assert optional_user_id(fake_request()) is None
