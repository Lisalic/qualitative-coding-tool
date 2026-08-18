"""Tests for backend/app/api/schemas.py -- Pydantic request/response models
and the `as_form` adapter.
"""

import pytest
from pydantic import ValidationError

from backend.app.api.schemas import (
    ApplyCodebookRequest,
    ApplyCodebookResponse,
    FilterDataRequest,
    FilterDataResponse,
    GenerateCodebookFileInfo,
    GenerateCodebookRequest,
    GenerateCodebookResponse,
)


# ---------------------------------------------------------------------------
# FilterDataRequest
# ---------------------------------------------------------------------------


class TestFilterDataRequest:
    def _minimal(self, **overrides):
        base = dict(api_key="k", database="proj_abc", name="n", model="m")
        base.update(overrides)
        return base

    def test_minimal_valid_payload(self) -> None:
        req = FilterDataRequest(**self._minimal())
        assert req.min_words == 0
        assert req.sample_percentage == 100.0
        assert req.project_id is None

    @pytest.mark.parametrize("field", ["api_key", "database", "name", "model"])
    def test_missing_required_field_raises(self, field: str) -> None:
        payload = self._minimal()
        del payload[field]
        with pytest.raises(ValidationError):
            FilterDataRequest(**payload)

    def test_empty_string_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            FilterDataRequest(**self._minimal(api_key=""))

    def test_database_pattern_rejects_non_proj_schema(self) -> None:
        with pytest.raises(ValidationError):
            FilterDataRequest(**self._minimal(database="not_proj"))

    def test_database_strips_trailing_db_suffix_before_pattern_check(self) -> None:
        req = FilterDataRequest(**self._minimal(database="proj_abc.db"))
        assert req.database == "proj_abc"

    def test_database_whitespace_stripped(self) -> None:
        req = FilterDataRequest(**self._minimal(database="  proj_abc  "))
        assert req.database == "proj_abc"

    def test_sample_percentage_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilterDataRequest(**self._minimal(sample_percentage=0))

    def test_sample_percentage_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilterDataRequest(**self._minimal(sample_percentage=101))

    def test_min_words_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilterDataRequest(**self._minimal(min_words=-1))

    def test_unknown_field_is_ignored_not_rejected(self) -> None:
        # _StrippingModel.model_config sets extra="ignore" (despite the
        # docstring claiming rejection) -- an unrecognized field must not
        # raise.
        req = FilterDataRequest(**self._minimal(), unexpected_field="x")
        assert not hasattr(req, "unexpected_field")

    def test_all_whitespace_name_is_stripped_to_empty_and_still_valid(self) -> None:
        # str_strip_whitespace strips before min_length is checked, so a
        # whitespace-only name is stripped first, THEN fails min_length.
        with pytest.raises(ValidationError):
            FilterDataRequest(**self._minimal(name="   "))


class TestFilterDataResponse:
    def test_requires_all_core_fields(self) -> None:
        with pytest.raises(ValidationError):
            FilterDataResponse(message="ok")  # missing counts

    def test_file_and_tag_filter_default_to_none(self) -> None:
        resp = FilterDataResponse(
            message="ok",
            submissions_length=1,
            comments_length=2,
            posts_filtered_count=1,
            comments_filtered_count=2,
        )
        assert resp.file is None
        assert resp.tag_filter is None


# ---------------------------------------------------------------------------
# GenerateCodebookRequest
# ---------------------------------------------------------------------------


class TestGenerateCodebookRequest:
    def _minimal(self, **overrides):
        base = dict(api_key="k", database="proj_abc", name="n")
        base.update(overrides)
        return base

    def test_model_is_optional(self) -> None:
        # Contrast with FilterDataRequest, where `model` is required.
        req = GenerateCodebookRequest(**self._minimal())
        assert req.model is None

    def test_sample_percentage_zero_is_valid_here(self) -> None:
        # ge=0.0 here, vs ge=1.0 on FilterDataRequest/ApplyCodebookRequest.
        req = GenerateCodebookRequest(**self._minimal(sample_percentage=0))
        assert req.sample_percentage == 0.0

    def test_sample_percentage_zero_rejected_on_filter_data(self) -> None:
        with pytest.raises(ValidationError):
            FilterDataRequest(api_key="k", database="proj_a", name="n", model="m", sample_percentage=0)

    def test_database_pattern_still_enforced(self) -> None:
        with pytest.raises(ValidationError):
            GenerateCodebookRequest(**self._minimal(database="bad"))


class TestGenerateCodebookResponse:
    def test_file_is_required_not_optional(self) -> None:
        with pytest.raises(ValidationError):
            GenerateCodebookResponse(codebook="text")  # missing `file`

    def test_valid_response(self) -> None:
        resp = GenerateCodebookResponse(
            codebook="text",
            file=GenerateCodebookFileInfo(id="1", schema_name="proj_a", filename="f"),
        )
        assert resp.file.description is None


# ---------------------------------------------------------------------------
# ApplyCodebookRequest
# ---------------------------------------------------------------------------


class TestApplyCodebookRequest:
    def _minimal(self, **overrides):
        base = dict(api_key="k", database="proj_abc", codebook="123", report_name="r")
        base.update(overrides)
        return base

    def test_numeric_codebook_id_accepted(self) -> None:
        req = ApplyCodebookRequest(**self._minimal(codebook="  7  "))
        assert req.codebook == "7"

    def test_proj_schema_codebook_accepted(self) -> None:
        req = ApplyCodebookRequest(**self._minimal(codebook="proj_abc"))
        assert req.codebook == "proj_abc"

    def test_proj_schema_codebook_has_no_db_suffix_stripping(self) -> None:
        # Unlike `database` (which strips a trailing .db via
        # _strip_db_suffix before pattern-matching), `codebook`'s own
        # validator has no such step, so a `.db`-suffixed schema name
        # fails the strict proj_<hex> pattern match.
        with pytest.raises(ValidationError):
            ApplyCodebookRequest(**self._minimal(codebook="proj_abc.db"))

    def test_negative_int_string_is_accepted_as_a_file_id(self) -> None:
        # The validator only checks `int(raw)` parses -- it does not
        # reject negative numbers, even though a negative File id can
        # never exist. A permissive quirk worth pinning down.
        req = ApplyCodebookRequest(**self._minimal(codebook="-1"))
        assert req.codebook == "-1"

    @pytest.mark.parametrize("bad", ["abc", "1.5", "file_3", "proj_"])
    def test_invalid_codebook_ref_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            ApplyCodebookRequest(**self._minimal(codebook=bad))

    def test_codebook_asymmetry_loose_startswith_check(self) -> None:
        # `codebook` only checks startswith("proj_") + the full pattern,
        # same regex as `database` -- "proj_a-b!" should fail the pattern
        # (hyphen not allowed) even though startswith("proj_") passes.
        with pytest.raises(ValidationError):
            ApplyCodebookRequest(**self._minimal(codebook="proj_a-b!"))

    def test_empty_codebook_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ApplyCodebookRequest(**self._minimal(codebook=""))

    def test_sample_percentage_zero_rejected(self) -> None:
        # ge=1.0 here (unlike GenerateCodebookRequest's ge=0.0).
        with pytest.raises(ValidationError):
            ApplyCodebookRequest(**self._minimal(sample_percentage=0))


class TestApplyCodebookResponse:
    def test_file_defaults_to_none(self) -> None:
        resp = ApplyCodebookResponse(classification_output="x")
        assert resp.file is None
