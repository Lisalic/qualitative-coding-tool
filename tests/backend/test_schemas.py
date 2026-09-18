"""Tests for backend/app/api/schemas.py -- Pydantic request/response models
and the `as_form` adapter.

Covers the editor request schemas for the three pipeline stages that have
one entry point each (filter, codebook, coding): an AI-assist preview
request, a manual-create request, and (for coding) the recode-selection
request. There is no one-shot request schema left to test -- the
one-shot filter-data/generate-codebook/apply-codebook endpoints and their
request/response models were retired in favor of these.
"""

import pytest
from pydantic import ValidationError

from backend.app.api.schemas import (
    AssistRunIn,
    CodebookCodeIn,
    CodebookPreviewRequest,
    CodingEntryIn,
    FilterPreviewRequest,
    ManualCodebookRequest,
    ManualCodingRequest,
    ManualFilterRequest,
    RecodeItemsRequest,
    SaveCodingRevisionRequest,
)


# ---------------------------------------------------------------------------
# FilterPreviewRequest
# ---------------------------------------------------------------------------


class TestFilterPreviewRequest:
    def _minimal(self, **overrides):
        base = dict(api_key="k", database="proj_abc", model="m", include_prompt="p")
        base.update(overrides)
        return base

    def test_minimal_valid_payload(self) -> None:
        req = FilterPreviewRequest(**self._minimal())
        assert req.min_words == 0
        assert req.sample_percentage == 100.0
        assert req.included_post_ids == []
        assert req.excluded_post_ids == []
        assert req.included_comment_ids == []
        assert req.excluded_comment_ids == []
        assert req.use_examples is False

    @pytest.mark.parametrize("field", ["api_key", "database", "model"])
    def test_missing_required_field_raises(self, field: str) -> None:
        payload = self._minimal()
        del payload[field]
        with pytest.raises(ValidationError):
            FilterPreviewRequest(**payload)

    def test_database_pattern_rejects_non_proj_schema(self) -> None:
        with pytest.raises(ValidationError):
            FilterPreviewRequest(**self._minimal(database="not_proj"))

    def test_database_strips_trailing_db_suffix_before_pattern_check(self) -> None:
        req = FilterPreviewRequest(**self._minimal(database="proj_abc.db"))
        assert req.database == "proj_abc"

    def test_sample_percentage_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilterPreviewRequest(**self._minimal(sample_percentage=0))

    def test_decided_ids_are_carried_through(self) -> None:
        req = FilterPreviewRequest(
            **self._minimal(
                included_post_ids=["p1", "p2"],
                included_comment_ids=["c1"],
                excluded_post_ids=["p3"],
                excluded_comment_ids=["c2"],
            )
        )
        assert req.included_post_ids == ["p1", "p2"]
        assert req.included_comment_ids == ["c1"]
        assert req.excluded_post_ids == ["p3"]
        assert req.excluded_comment_ids == ["c2"]

    def test_no_criteria_no_tags_no_examples_rejected(self) -> None:
        payload = self._minimal()
        del payload["include_prompt"]
        with pytest.raises(ValidationError):
            FilterPreviewRequest(**payload)

    def test_exclude_prompt_alone_is_sufficient(self) -> None:
        payload = self._minimal()
        del payload["include_prompt"]
        req = FilterPreviewRequest(**payload, exclude_prompt="drop spam")
        assert req.exclude_prompt == "drop spam"

    def test_filter_tags_alone_is_sufficient(self) -> None:
        payload = self._minimal()
        del payload["include_prompt"]
        req = FilterPreviewRequest(**payload, filter_tags="anxiety")
        assert req.filter_tags == "anxiety"

    def test_use_examples_without_prompts_is_valid_when_decisions_exist(self) -> None:
        payload = self._minimal()
        del payload["include_prompt"]
        req = FilterPreviewRequest(**payload, use_examples=True, included_post_ids=["p1"])
        assert req.use_examples is True

    def test_use_examples_without_any_decision_rejected(self) -> None:
        payload = self._minimal()
        del payload["include_prompt"]
        with pytest.raises(ValidationError):
            FilterPreviewRequest(**payload, use_examples=True)


# ---------------------------------------------------------------------------
# ManualFilterRequest
# ---------------------------------------------------------------------------


class TestManualFilterRequest:
    def _minimal(self, **overrides):
        base = dict(database="proj_abc", name="n", post_ids=["p1"], project_id=1)
        base.update(overrides)
        return base

    def test_minimal_valid_payload(self) -> None:
        req = ManualFilterRequest(**self._minimal())
        assert req.comment_ids == []
        assert req.project_id == 1

    def test_project_is_required(self) -> None:
        # Every artifact belongs to a project -- there is no "no project".
        payload = self._minimal()
        payload.pop("project_id")
        with pytest.raises(ValidationError):
            ManualFilterRequest(**payload)

    def test_carries_no_api_key_or_model(self) -> None:
        # Submitting a manual filter involves no LLM call, unlike the
        # preview step -- there is no api_key/model field to require.
        req = ManualFilterRequest(**self._minimal())
        assert not hasattr(req, "api_key")
        assert not hasattr(req, "model")

    def test_at_least_one_row_required(self) -> None:
        with pytest.raises(ValidationError):
            ManualFilterRequest(database="proj_abc", name="n", project_id=1)

    def test_comment_ids_alone_satisfy_the_at_least_one_row_rule(self) -> None:
        req = ManualFilterRequest(
            database="proj_abc", name="n", comment_ids=["c1"], project_id=1
        )
        assert req.post_ids == []

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ManualFilterRequest(database="proj_abc", post_ids=["p1"], project_id=1)


# ---------------------------------------------------------------------------
# CodebookPreviewRequest
# ---------------------------------------------------------------------------


class TestCodebookPreviewRequest:
    def _minimal(self, **overrides):
        base = dict(api_key="k", database="proj_abc", model="m")
        base.update(overrides)
        return base

    def test_minimal_valid_payload(self) -> None:
        req = CodebookPreviewRequest(**self._minimal())
        assert req.existing_codes == []
        assert req.sample_percentage == 100.0

    def test_sample_percentage_below_one_rejected(self) -> None:
        # ge=1.0 here -- unlike the old GenerateCodebookRequest's ge=0.0,
        # a preview run always samples something.
        with pytest.raises(ValidationError):
            CodebookPreviewRequest(**self._minimal(sample_percentage=0))

    def test_database_pattern_still_enforced(self) -> None:
        with pytest.raises(ValidationError):
            CodebookPreviewRequest(**self._minimal(database="bad"))

    def test_existing_codes_accepted_as_narrow_refs(self) -> None:
        req = CodebookPreviewRequest(
            **self._minimal(existing_codes=[{"name": "Trust", "definition": "d"}])
        )
        assert req.existing_codes[0].name == "Trust"
        assert req.existing_codes[0].family_name == ""


# ---------------------------------------------------------------------------
# ManualCodebookRequest
# ---------------------------------------------------------------------------


class TestManualCodebookRequest:
    def _code(self, **overrides):
        base = dict(is_new=True, family_name="Fam", family_is_new=True, name="Code")
        base.update(overrides)
        return base

    def _minimal(self, **overrides):
        base = dict(database="proj_abc", name="n", codes=[self._code()], project_id=1)
        base.update(overrides)
        return base

    def test_minimal_valid_payload(self) -> None:
        req = ManualCodebookRequest(**self._minimal())
        assert len(req.codes) == 1
        assert isinstance(req.codes[0], CodebookCodeIn)

    def test_carries_no_api_key_or_model(self) -> None:
        req = ManualCodebookRequest(**self._minimal())
        assert not hasattr(req, "api_key")
        assert not hasattr(req, "model")

    def test_at_least_one_code_required(self) -> None:
        with pytest.raises(ValidationError):
            ManualCodebookRequest(database="proj_abc", name="n", codes=[], project_id=1)

    def test_project_is_required(self) -> None:
        payload = self._minimal()
        payload.pop("project_id")
        with pytest.raises(ValidationError):
            ManualCodebookRequest(**payload)

    def test_database_pattern_still_enforced(self) -> None:
        with pytest.raises(ValidationError):
            ManualCodebookRequest(**self._minimal(database="bad"))


# ---------------------------------------------------------------------------
# ManualCodingRequest
# ---------------------------------------------------------------------------


class TestManualCodingRequest:
    def _minimal(self, **overrides):
        base = dict(database="proj_abc", codebook="123", report_name="r", project_id=1)
        base.update(overrides)
        return base

    def test_minimal_valid_payload(self) -> None:
        req = ManualCodingRequest(**self._minimal())
        assert req.post_ids == []
        assert req.comment_ids == []
        assert req.sample_percentage == 100.0

    def test_project_is_required(self) -> None:
        payload = self._minimal()
        payload.pop("project_id")
        with pytest.raises(ValidationError):
            ManualCodingRequest(**payload)

    def test_carries_no_api_key_or_model(self) -> None:
        # The coding editor's only creation path -- no classifier runs,
        # so there is nothing here for an api_key/model/methodology.
        req = ManualCodingRequest(**self._minimal())
        assert not hasattr(req, "api_key")
        assert not hasattr(req, "model")
        assert not hasattr(req, "methodology")

    def test_numeric_codebook_id_accepted(self) -> None:
        req = ManualCodingRequest(**self._minimal(codebook="  7  "))
        assert req.codebook == "7"

    def test_proj_schema_codebook_accepted(self) -> None:
        req = ManualCodingRequest(**self._minimal(codebook="proj_abc"))
        assert req.codebook == "proj_abc"

    @pytest.mark.parametrize("bad", ["abc", "1.5", "file_3", "proj_"])
    def test_invalid_codebook_ref_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            ManualCodingRequest(**self._minimal(codebook=bad))

    def test_missing_report_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ManualCodingRequest(database="proj_abc", codebook="123")

    def test_explicit_row_ids_are_carried_through(self) -> None:
        req = ManualCodingRequest(**self._minimal(post_ids=["p1"], comment_ids=["c1"]))
        assert req.post_ids == ["p1"]
        assert req.comment_ids == ["c1"]


# ---------------------------------------------------------------------------
# RecodeItemsRequest
# ---------------------------------------------------------------------------


class TestRecodeItemsRequest:
    def test_minimal_valid_payload(self) -> None:
        req = RecodeItemsRequest(api_key="k", item_ids=["p_1", "c_2"], model="m")
        assert req.model == "m"
        assert req.methodology is None

    def test_missing_api_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            RecodeItemsRequest(item_ids=["p_1"], model="m")

    def test_at_least_one_item_id_required(self) -> None:
        with pytest.raises(ValidationError):
            RecodeItemsRequest(api_key="k", item_ids=[], model="m")

    def test_missing_model_raises(self) -> None:
        with pytest.raises(ValidationError):
            RecodeItemsRequest(api_key="k", item_ids=["p_1"])


# ---------------------------------------------------------------------------
# CodingEntryIn -- B1 per-quote coder attribution
# ---------------------------------------------------------------------------


class TestCodingEntryIn:
    def _minimal(self, **overrides):
        base = dict(code_uid="u1", quote="e", start_offset=0, end_offset=1)
        base.update(overrides)
        return base

    def test_defaults_to_human_with_no_job(self) -> None:
        entry = CodingEntryIn(**self._minimal())
        assert entry.coder == "human"
        assert entry.assist_job_id is None

    def test_ai_requires_assist_job_id(self) -> None:
        with pytest.raises(ValidationError):
            CodingEntryIn(**self._minimal(coder="ai"))

    def test_ai_with_assist_job_id_is_valid(self) -> None:
        entry = CodingEntryIn(**self._minimal(coder="ai", assist_job_id=7))
        assert entry.coder == "ai"
        assert entry.assist_job_id == 7

    def test_human_cannot_carry_an_assist_job_id(self) -> None:
        with pytest.raises(ValidationError):
            CodingEntryIn(**self._minimal(coder="human", assist_job_id=7))

    def test_unknown_coder_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CodingEntryIn(**self._minimal(coder="robot", assist_job_id=1))


# ---------------------------------------------------------------------------
# AssistRunIn / SaveCodingRevisionRequest -- C2 provenance channel
# ---------------------------------------------------------------------------


class TestAssistRunIn:
    def test_minimal_valid_payload(self) -> None:
        run = AssistRunIn(job_id=1)
        assert run.proposed_count == 0
        assert run.accepted_count == 0
        assert run.dismissed_count == 0
        assert run.accepted_refs is None

    def test_job_id_required(self) -> None:
        with pytest.raises(ValidationError):
            AssistRunIn()

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssistRunIn(job_id=1, accepted_count=-1)

    def test_carries_no_model_or_prompt_fields(self) -> None:
        run = AssistRunIn(job_id=1)
        assert not hasattr(run, "model")
        assert not hasattr(run, "system_prompt")


class TestSaveCodingRevisionRequest:
    def test_carries_no_model_or_job_id(self) -> None:
        """Regression guard for the removed leak -- see
        versioning_models.ArtifactAssist's docstring for why model/job_id
        no longer belong on this request.
        """
        req = SaveCodingRevisionRequest(codes=[{"is_new": True, "family_name": "F", "family_is_new": True, "name": "C"}])
        assert not hasattr(req, "model")
        assert not hasattr(req, "job_id")

    def test_assist_runs_defaults_empty(self) -> None:
        req = SaveCodingRevisionRequest(codes=[{"is_new": True, "family_name": "F", "family_is_new": True, "name": "C"}])
        assert req.assist_runs == []

    def test_assist_runs_accepted(self) -> None:
        req = SaveCodingRevisionRequest(
            codes=[{"is_new": True, "family_name": "F", "family_is_new": True, "name": "C"}],
            assist_runs=[{"job_id": 5, "accepted_count": 2}],
        )
        assert len(req.assist_runs) == 1
        assert req.assist_runs[0].job_id == 5

    def test_at_least_one_of_codes_rows_still_required(self) -> None:
        with pytest.raises(ValidationError):
            SaveCodingRevisionRequest()

