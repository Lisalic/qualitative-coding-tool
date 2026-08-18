from backend.app.core.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UpstreamServiceError,
    ValidationAppError,
)


class TestStatusCodes:
    def test_app_error_defaults_to_500(self) -> None:
        assert AppError("boom").status_code == 500

    def test_not_found_is_404(self) -> None:
        assert NotFoundError("x").status_code == 404

    def test_forbidden_is_403(self) -> None:
        assert ForbiddenError("x").status_code == 403

    def test_unauthorized_is_401(self) -> None:
        assert UnauthorizedError("x").status_code == 401

    def test_validation_is_400(self) -> None:
        assert ValidationAppError("x").status_code == 400

    def test_upstream_service_is_502(self) -> None:
        assert UpstreamServiceError("x").status_code == 502


class TestMessage:
    def test_message_preserved_on_instance_and_str(self) -> None:
        exc = NotFoundError("thing not found")
        assert exc.message == "thing not found"
        assert str(exc) == "thing not found"

    def test_all_are_exceptions(self) -> None:
        assert isinstance(NotFoundError("x"), AppError)
        assert isinstance(AppError("x"), Exception)
