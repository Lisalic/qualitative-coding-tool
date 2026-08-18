import pytest

from backend.app.jobs.registry import get_handler, register_handler


class TestRegisterAndGetHandler:
    def test_registered_handler_is_returned(self) -> None:
        @register_handler("registry_test_type_a")
        async def handler(job_id: int, payload: dict) -> dict:
            return {"job_id": job_id, **payload}

        assert get_handler("registry_test_type_a") is handler

    def test_unknown_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="registry_test_type_unregistered"):
            get_handler("registry_test_type_unregistered")

    def test_decorator_returns_original_function(self) -> None:
        async def handler(job_id: int, payload: dict) -> dict:
            return {}

        decorated = register_handler("registry_test_type_b")(handler)
        assert decorated is handler
