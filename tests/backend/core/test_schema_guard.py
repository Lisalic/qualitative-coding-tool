import pytest

from backend.app.core.exceptions import ValidationAppError
from backend.app.core.schema_guard import (
    is_valid_artifact_schema,
    normalize_schema,
    require_valid_schema,
)


class TestNormalizeSchema:
    def test_none_returns_empty_string(self) -> None:
        assert normalize_schema(None) == ""

    def test_strips_whitespace_and_db_suffix(self) -> None:
        assert normalize_schema("  proj_a.db  ") == "proj_a"

    def test_no_suffix_unchanged(self) -> None:
        assert normalize_schema("proj_a") == "proj_a"


class TestIsValidArtifactSchema:
    @pytest.mark.parametrize("name", ["proj_a", "cmp_a", "sum_a"])
    def test_default_prefixes_accept_all_artifact_types(self, name) -> None:
        assert is_valid_artifact_schema(name) is True

    def test_custom_prefixes_restrict_to_given_set(self) -> None:
        assert is_valid_artifact_schema("cmp_a", allowed_prefixes=("proj_",)) is False
        assert is_valid_artifact_schema("proj_a", allowed_prefixes=("proj_",)) is True

    def test_empty_name_is_invalid(self) -> None:
        assert is_valid_artifact_schema("") is False


class TestRequireValidSchema:
    def test_valid_name_is_normalized_and_returned(self) -> None:
        assert require_valid_schema("  proj_a.db  ") == "proj_a"

    def test_invalid_name_raises_validation_error(self) -> None:
        with pytest.raises(ValidationAppError):
            require_valid_schema('proj_a"; DROP TABLE x; --')

    def test_none_raises_validation_error(self) -> None:
        with pytest.raises(ValidationAppError):
            require_valid_schema(None)

    def test_custom_field_name_in_message(self) -> None:
        with pytest.raises(ValidationAppError, match="Invalid codebook name"):
            require_valid_schema("not valid", field_name="codebook")
