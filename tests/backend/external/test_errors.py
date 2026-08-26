import pytest

from backend.app.external.errors import (
    ExternalServiceError,
    extract_http_error_code,
    is_retryable_error,
)


class TestExtractHttpErrorCode:
    def test_error_code_pattern_in_message(self) -> None:
        assert extract_http_error_code(Exception("Error code: 429 - rate limited")) == 429

    def test_status_code_attribute(self) -> None:
        class FakeError(Exception):
            status_code = 401

        assert extract_http_error_code(FakeError("bad key")) == 401

    def test_no_match_returns_zero(self) -> None:
        assert extract_http_error_code(Exception("something else entirely")) == 0

    def test_message_pattern_takes_priority_over_attribute(self) -> None:
        class FakeError(Exception):
            status_code = 500

        assert extract_http_error_code(FakeError("Error code: 404 not found")) == 404


class TestExternalServiceError:
    def test_default_code_is_zero(self) -> None:
        exc = ExternalServiceError("boom")
        assert exc.code == 0
        assert exc.message == "boom"

    def test_explicit_code(self) -> None:
        exc = ExternalServiceError("boom", code=502)
        assert exc.code == 502


class TestIsRetryableError:
    @pytest.mark.parametrize("code", [400, 401, 402, 403, 404])
    def test_permanent_request_errors_are_not_retryable(self, code) -> None:
        assert is_retryable_error(Exception(f"Error code: {code} - boom")) is False

    @pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
    def test_transient_errors_are_retryable(self, code) -> None:
        assert is_retryable_error(Exception(f"Error code: {code} - boom")) is True

    def test_empty_completion_with_no_code_is_retryable(self) -> None:
        # ExternalServiceError("OpenRouter returned an empty completion")
        # carries no code at all -- treated as transient (a free model
        # being briefly overloaded), same as before this change.
        assert is_retryable_error(ExternalServiceError("OpenRouter returned an empty completion")) is True

    def test_unknown_exception_with_no_code_is_retryable(self) -> None:
        assert is_retryable_error(Exception("connection reset")) is True
