from backend.app.external.errors import ExternalServiceError, extract_http_error_code


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
