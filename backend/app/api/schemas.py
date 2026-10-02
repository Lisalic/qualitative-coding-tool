"""Pydantic request/response contracts for the filter/codebook/coding editors.

These models are the single source of truth for the shape of data sent from
the frontend `FormData` builders to the FastAPI handlers. They are consumed
by the routes through :func:`as_form`, which adapts a Pydantic model into a
FastAPI `Depends`-able that reads `multipart/form-data` fields.

Keeping the wire format as `multipart/form-data` means the frontend tool
panels don't have to change their transport, while the backend gets strict
field-level validation (422 on bad input) and accurate OpenAPI docs.
"""
from __future__ import annotations

import inspect
import re
from typing import Any, Literal, Optional, Type, TypeVar

from fastapi import Form
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

T = TypeVar("T", bound=BaseModel)


_SCHEMA_PATTERN = r"^proj_[A-Za-z0-9_]+$"
_COMPARISON_SCHEMA_PATTERN = r"^cmp_[A-Za-z0-9_]+$"

ContentScope = Literal["both", "posts", "comments"]


def _content_scope_field() -> Any:
    """Which of a source file's submissions/comments tables an AI tool
    should sample from. Shared across the filter/codebook/apply editors'
    AI-assist and manual-create builders in apiContracts.js so they all
    send the same field name. Defaults to "both" -- today's behavior for
    every one of these tools, unchanged for any existing caller that
    doesn't send this field.
    """
    return Field(
        default="both",
        description="Which content types to sample: 'both', 'posts', or 'comments'",
    )


def _strip_db_suffix_value(value: Any) -> Any:
    """Normalize a source-database identifier: trim, and drop a trailing
    ``.db`` the frontend sometimes carries on a display name. Shared by
    every request model with a ``database`` field so they cannot drift.
    """
    if not isinstance(value, str):
        return value
    value = value.strip()
    if value.endswith(".db"):
        value = value[:-3]
    return value


def _validate_codebook_ref_value(value: str) -> str:
    """A codebook reference is either a numeric ``File`` id or a
    ``proj_<hex>`` schema name -- both accepted, nothing else. Used by
    ``ManualCodingRequest``, which resolves it through
    ``file_repo.resolve_file_id``.
    """
    raw = value.strip()
    if not raw:
        raise ValueError("codebook must not be empty")
    if raw.startswith("proj_"):
        if not re.match(_SCHEMA_PATTERN, raw):
            raise ValueError("codebook schema must match proj_<hex>")
        return raw
    try:
        int(raw)
    except ValueError as exc:
        raise ValueError(
            "codebook must be a numeric File id or a proj_<hex> schema name"
        ) from exc
    return raw


def as_form(cls: Type[T]):
    """Adapt a Pydantic model into a FastAPI dependency that reads form fields.

    The returned callable has an ``inspect.Signature`` that mirrors the model's
    fields, each with a ``Form(...)`` default. FastAPI introspects this
    signature to build the multipart parser. Validation errors produced by the
    Pydantic constructor propagate as ``RequestValidationError`` (HTTP 422).
    """
    parameters: list[inspect.Parameter] = []
    for field_name, field_info in cls.model_fields.items():
        if field_info.is_required():
            form_default: Any = Form(...)
        else:
            form_default = Form(field_info.default)
        parameters.append(
            inspect.Parameter(
                name=field_name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=form_default,
                annotation=field_info.annotation,
            )
        )

    async def _as_form(**data: Any) -> T:
        try:
            return cls(**data)
        except ValidationError as exc:
            # FastAPI only converts ValidationError -> 422 when it happens
            # during its own parameter-solving. Pydantic v2 raises its own
            # ValidationError type, so we re-raise it as the one FastAPI knows.
            raise RequestValidationError(errors=exc.errors()) from exc

    _as_form.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    _as_form.__name__ = f"as_form_{cls.__name__}"
    return _as_form


class _StrippingModel(BaseModel):
    """Shared config: whitespace is stripped, unknown fields are ignored."""

    model_config = {
        "str_strip_whitespace": True,
        "extra": "ignore",
    }


# ---------------------------------------------------------------------------
# Filter editor: AI preview + manual submit
#
# The two halves of the human-in-the-loop filter screen
# (`frontend/src/components/filter-editor/`), which composes a
# `filtered_data` artifact from rows the user checked by hand, with the
# AI filter available inside it as an assistive tool rather than as the
# whole operation.
#
# Both are JSON bodies rather than `as_form` multipart: each carries id
# lists, and the codebase's rule is multipart for flat AI-tool forms and
# JSON for anything with a nested list (same reasoning as
# `RecodeItemsRequest`).
#
# `FilterPreviewRequest` deliberately has no `name`/`project_id`: a
# preview creates no artifact at all, it only answers "which of the rows
# I haven't decided on yet would you keep?".
# ---------------------------------------------------------------------------


class FilterPreviewRequest(_StrippingModel):
    """Payload for ``POST /api/filter-preview/``.

    The AI-triage knobs (separate ``include_prompt``/``exclude_prompt``,
    tags, model, ``min_words``, sampling, content scope), plus the four
    lists that make it a *preview*: ``included_*_ids``/``excluded_*_ids``
    are the rows the user has already explicitly included or excluded in
    the editor. They are removed from the candidate pool before sampling
    -- so re-running the tool never re-litigates a decision the human
    already made, and each run only proposes rows that are still
    undecided.

    ``use_examples`` selects "Autofill with AI": when true, the two
    prompts are ignored and the already-decided rows are rendered as
    labelled "similar examples" instead, so the model imitates the
    researcher's own judgement rather than following new criteria.

    The frontend builder is ``buildFilterPreviewPayload`` in
    ``frontend/src/lib/apiContracts.js``.
    """

    api_key: str = Field(min_length=1, description="OpenRouter API key from the client")
    database: str = Field(pattern=_SCHEMA_PATTERN, description="Source schema (proj_<hex>)")
    model: str = Field(min_length=1, description="OpenRouter model slug")
    include_prompt: Optional[str] = Field(default=None)
    exclude_prompt: Optional[str] = Field(default=None)
    use_examples: bool = Field(
        default=False, description="Autofill from prior decisions instead of the prompts above"
    )
    filter_tags: Optional[str] = Field(default=None)
    min_words: int = Field(default=0, ge=0)
    sample_percentage: float = Field(default=100.0, ge=1.0, le=100.0)
    content_scope: ContentScope = _content_scope_field()
    included_post_ids: list[str] = Field(
        default_factory=list,
        description="Submission ids the user already included",
    )
    included_comment_ids: list[str] = Field(
        default_factory=list,
        description="Comment ids the user already included",
    )
    excluded_post_ids: list[str] = Field(
        default_factory=list,
        description="Submission ids the user already excluded",
    )
    excluded_comment_ids: list[str] = Field(
        default_factory=list,
        description="Comment ids the user already excluded",
    )

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.endswith(".db"):
            value = value[:-3]
        return value

    @model_validator(mode="after")
    def _has_criteria(self):
        """Mirrors ``data_service.start_filter_preview_job``'s guard, so a
        request with nothing to go on fails fast with a 422 instead of
        reaching the job queue.
        """
        has_decisions = bool(
            self.included_post_ids
            or self.included_comment_ids
            or self.excluded_post_ids
            or self.excluded_comment_ids
        )
        if self.use_examples and not has_decisions:
            raise ValueError("Autofill needs at least one row already included or excluded")
        if not self.use_examples and not (self.include_prompt or "").strip() and not (
            self.exclude_prompt or ""
        ).strip() and not (self.filter_tags or "").strip():
            raise ValueError("An include or exclude criterion is required")
        return self


class AssistRunIn(_StrippingModel):
    """One assistant run's accept/dismiss bookkeeping, as recorded by an
    editor -- the C2 provenance channel
    (``services/assist_service.py``) that closes GAP-4 without touching
    ``origin``/``model`` on the version itself.

    Deliberately carries no ``model``/``system_prompt``/prompt text:
    those are read server-side from the referenced ``job_id``'s own
    payload/result, never trusted from the client (see
    ``assist_service.record_assist_runs``) -- a request can name which
    run happened, not what that run produced.
    """

    job_id: int
    proposed_count: int = Field(default=0, ge=0)
    accepted_count: int = Field(default=0, ge=0)
    dismissed_count: int = Field(default=0, ge=0)
    accepted_refs: Optional[list[str]] = None


class ManualFilterRequest(_StrippingModel):
    """Payload for ``POST /api/filtered-data/manual``.

    The submit half of the filter editor: the final set of rows the user
    checked, whatever mix of hand-picked and AI-suggested-then-accepted
    produced it. There is no prompt or model here by design -- provenance
    for an AI assist during editing is not the same claim as "an LLM
    produced this artifact", so the resulting version is recorded as
    ``origin="edited"`` with no ``system_prompt``. ``assist_runs`` is the
    separate channel that DOES record the assist -- see
    ``AssistRunIn``.

    The frontend builder is ``buildManualFilterPayload`` in
    ``frontend/src/lib/apiContracts.js``.
    """

    database: str = Field(pattern=_SCHEMA_PATTERN, description="Source schema (proj_<hex>)")
    name: str = Field(min_length=1, description="Display name for the new filtered file")
    description: Optional[str] = Field(default=None)
    project_id: int = Field(description="Owning project -- every artifact belongs to one")
    post_ids: list[str] = Field(default_factory=list)
    comment_ids: list[str] = Field(default_factory=list)
    assist_runs: list[AssistRunIn] = Field(default_factory=list)

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.endswith(".db"):
            value = value[:-3]
        return value

    @model_validator(mode="after")
    def _at_least_one_row(self):
        """An empty filtered database is never what the user meant, and
        it would otherwise be indistinguishable from a lost selection.
        """
        if not self.post_ids and not self.comment_ids:
            raise ValueError("At least one of post_ids/comment_ids is required")
        return self


# ---------------------------------------------------------------------------
# Row memos
#
# One memo per (file, row_type, row_id) -- see `storage_models.py::RowMemo`
# for why memos are neither range-versioned nor threaded.
# ---------------------------------------------------------------------------


class MemoUpsertRequest(_StrippingModel):
    """Payload for ``PUT /api/memos/``.

    A blank ``body`` clears the memo rather than storing an empty one, so
    ``body`` is deliberately not ``min_length=1``: "delete this memo" and
    "save this memo" are the same idempotent call, which is what makes
    ``PUT`` the right verb.
    """

    schema_: str = Field(alias="schema", pattern=_SCHEMA_PATTERN)
    row_type: Literal["submission", "comment"]
    row_id: str = Field(min_length=1)
    body: str = Field(default="")


# ---------------------------------------------------------------------------
# Codebook editor -- an AI-assist preview and a manual submit, mirroring
# the FilterPreview/ManualFilter pair.
#
# Both are JSON bodies rather than `as_form` multipart, because each carries
# a nested list (the same reasoning as FilterPreviewRequest). The split is
# deliberate: the preview request has no `name`/`project_id` because it
# creates nothing, and the manual request has no `api_key`/`model` because it
# calls no model.
# ---------------------------------------------------------------------------


class ExistingCodeRef(BaseModel):
    """One code already in the researcher's draft, sent to the preview job
    so the model is asked for what's *missing* rather than a fresh
    taxonomy. Deliberately narrow -- family/name/definition is everything
    the prompt needs; sending whole code rows would just inflate the
    reserved prompt budget.
    """

    family_name: str = ""
    name: str = Field(min_length=1)
    definition: Optional[str] = None


class CodebookPreviewRequest(_StrippingModel):
    """Payload for ``POST /api/codebook-preview/`` -- ask the model for
    codes to add to a draft. Creates nothing; see
    ``codebook_service._run_codebook_preview_job``.
    """

    api_key: str = Field(min_length=1)
    database: str = Field(pattern=_SCHEMA_PATTERN)
    model: str = Field(min_length=1)
    prompt: Optional[str] = None
    sample_percentage: float = Field(default=100.0, ge=1.0, le=100.0)
    content_scope: ContentScope = _content_scope_field()
    # Legitimately empty on a first pass, so not required -- same reasoning
    # as FilterPreviewRequest.included_post_ids.
    existing_codes: list[ExistingCodeRef] = Field(default_factory=list)

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        return _strip_db_suffix_value(value)


def _validate_codebook_schema_list(value: Any) -> Any:
    """Normalize a list of source-codebook refs: strip each entry (via
    ``_strip_db_suffix_value``) and drop exact duplicates while
    preserving order. Shared by ``IntegrateCodebookPreviewRequest`` and
    ``IntegrateCodebookRequest`` so both agree on what "the same
    codebook selected twice" means.
    """
    if not isinstance(value, list):
        return value
    seen: set[str] = set()
    normalized: list[Any] = []
    for entry in value:
        cleaned = _strip_db_suffix_value(entry)
        if isinstance(cleaned, str):
            if cleaned in seen:
                continue
            seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


class IntegrateCodebookPreviewRequest(_StrippingModel):
    """Payload for ``POST /api/integrate-codebook-preview/`` -- ask the
    model to merge two or more codebooks into a review tray of proposed
    codes. Creates nothing; see
    ``codebook_service._run_integrate_codebook_job``.
    """

    api_key: str = Field(min_length=1)
    codebooks: list[str] = Field(min_length=2, description="Source codebook schema names to merge")
    model: str = Field(min_length=1)
    prompt: Optional[str] = None
    existing_codes: list[ExistingCodeRef] = Field(default_factory=list)
    comparisons: list[str] = Field(
        default_factory=list,
        description="Codebook comparison schema names (cmp_<id>) to give the model as merge guidance",
    )

    @field_validator("codebooks", mode="before")
    @classmethod
    def _normalize_codebooks(cls, value: Any) -> Any:
        return _validate_codebook_schema_list(value)

    @field_validator("codebooks")
    @classmethod
    def _codebooks_are_proj_schemas(cls, value: list[str]) -> list[str]:
        for ref in value:
            if not re.match(_SCHEMA_PATTERN, ref or ""):
                raise ValueError(f"Invalid codebook reference: {ref!r}")
        return value

    @field_validator("comparisons", mode="before")
    @classmethod
    def _normalize_comparisons(cls, value: Any) -> Any:
        return _validate_codebook_schema_list(value)

    @field_validator("comparisons")
    @classmethod
    def _comparisons_are_cmp_schemas(cls, value: list[str]) -> list[str]:
        for ref in value:
            if not re.match(_COMPARISON_SCHEMA_PATTERN, ref or ""):
                raise ValueError(f"Invalid comparison reference: {ref!r}")
        return value


class IntegrateCodebookRequest(_StrippingModel):
    """Payload for ``POST /api/codebook/integrate`` -- create a codebook
    from the integrate editor's hand-reviewed merge draft. ``assist_runs``
    (see ``AssistRunIn``) is the C2 provenance channel for any
    AI-proposed merges that were accepted into ``codes``; it never
    changes ``codes``' own ``origin=edited`` recording.
    """

    codebooks: list[str] = Field(min_length=2, description="Source codebook schema names being integrated")
    name: str = Field(min_length=1)
    description: Optional[str] = None
    project_id: int = Field(description="Owning project -- every artifact belongs to one")
    codes: list[CodebookCodeIn] = Field(min_length=1)
    assist_runs: list[AssistRunIn] = Field(default_factory=list)

    @field_validator("codebooks", mode="before")
    @classmethod
    def _normalize_codebooks(cls, value: Any) -> Any:
        return _validate_codebook_schema_list(value)

    @field_validator("codebooks")
    @classmethod
    def _codebooks_are_proj_schemas(cls, value: list[str]) -> list[str]:
        for ref in value:
            if not re.match(_SCHEMA_PATTERN, ref or ""):
                raise ValueError(f"Invalid codebook reference: {ref!r}")
        return value


class ManualCodebookRequest(_StrippingModel):
    """Payload for ``POST /api/codebook/manual`` -- create a codebook from
    the editor's hand-composed draft. ``assist_runs`` (see
    ``AssistRunIn``) is the C2 provenance channel for any AI-suggested
    codes that were accepted into ``codes``; it never changes ``codes``'
    own ``origin=edited`` recording.
    """

    database: str = Field(pattern=_SCHEMA_PATTERN)
    name: str = Field(min_length=1)
    description: Optional[str] = None
    project_id: int = Field(description="Owning project -- every artifact belongs to one")
    codes: list[CodebookCodeIn] = Field(min_length=1)
    assist_runs: list[AssistRunIn] = Field(default_factory=list)

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        return _strip_db_suffix_value(value)


# ---------------------------------------------------------------------------
# CompareCodebooks
# ---------------------------------------------------------------------------


class CompareCodebooksRequest(_StrippingModel):
    """Payload for ``POST /api/compare-codebooks/``."""

    codebook_a: str = Field(pattern=_SCHEMA_PATTERN)
    codebook_b: str = Field(pattern=_SCHEMA_PATTERN)
    api_key: str = Field(min_length=1)
    name: str = Field(min_length=1, description="Display name for the comparison")
    model: str = Field(min_length=1, description="OpenRouter model slug")
    prompt: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    project_id: int = Field(description="Owning project -- every artifact belongs to one")


# ---------------------------------------------------------------------------
# AI coding output (backend/scripts/codebook_apply.py::classify_posts)
#
# The shape the model is asked to return: one object per (item, code)
# pair, each carrying every quote it found in that item's own content
# supporting that code. Parsed with this model (rather than a bare
# ``json.loads``) so a malformed entry from a weak model is a normal,
# per-entry Pydantic ``ValidationError`` -- caught and dropped -- instead
# of a ``KeyError``/``TypeError`` surfacing from hand-written dict access.
# Existence/hallucination checks (does ``item_id`` exist? does ``code``
# exist in the codebook? does each quote actually occur in that item's
# text?) happen after this parse, in ``coding_service`` -- this model only
# validates *shape*, not truth.
# ---------------------------------------------------------------------------


class AICodingEntry(BaseModel):
    item_id: str
    code: str
    quotes: list[str] = Field(default_factory=list)


class AICodingPayload(BaseModel):
    codings: list[AICodingEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Coding artifact (structured coding_entries; see storage_models.CodingEntry)
#
# A coding artifact now owns its own codebook snapshot, its own copy of
# every sampled post/comment, and its coding -- these back the editor and
# recode routes in coding_routes.py. Sent as JSON bodies, not
# multipart/form-data, since a per-row list of code/evidence/notes
# entries doesn't map onto flat form fields the way the editors' scalar
# fields do -- same reasoning as ``PostContentsRequest`` below.
# ---------------------------------------------------------------------------


class CodingEntryIn(_StrippingModel):
    """One quote coded to one item -- the unit ``coding_entries`` now
    stores one row per (see ``storage_models.CodingEntry``). ``start_offset``/
    ``end_offset`` are character offsets into that item's own body text
    (``Submission.selftext``/``Comment.body``) and must satisfy
    ``0 <= start_offset < end_offset``; the frontend computes them directly
    from the real DOM selection range (see ``HighlightedContent.jsx``), so
    unlike AI output there is no separate existence/offset check at this
    boundary -- a manual edit is trusted the same way it always has been.

    ``code_uid`` (not a name string) identifies the code -- it must
    resolve against the coding artifact's own current codebook snapshot
    (``coding_service.save_coding_revision`` rejects one that doesn't), so
    a code rename never orphans a manually-entered quote.

    ``coder``/``assist_job_id`` are B1's per-quote attribution (see
    ``storage_models.CodingEntry``): a hand-added or hand-edited quote is
    ``coder="human"`` with no job; an accepted-as-is AI recode proposal
    is ``coder="ai"`` with the recode's ``job_id``, which
    ``coding_service.save_coding_revision`` validates the same way
    ``assist_service`` validates an ``AssistRunIn`` -- the client names
    which job produced it, the server confirms that job actually ran
    against this artifact before trusting the claim.
    """

    code_uid: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    notes: Optional[str] = None
    coder: Literal["human", "ai"] = "human"
    assist_job_id: Optional[int] = None

    @field_validator("end_offset")
    @classmethod
    def _end_after_start(cls, end_offset: int, info) -> int:
        start_offset = info.data.get("start_offset")
        if start_offset is not None and end_offset <= start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return end_offset

    @model_validator(mode="after")
    def _ai_requires_job(self):
        if self.coder == "ai" and not self.assist_job_id:
            raise ValueError("coder='ai' requires assist_job_id")
        if self.coder == "human" and self.assist_job_id is not None:
            raise ValueError("assist_job_id is only valid with coder='ai'")
        return self


class CodingRowUpdate(_StrippingModel):
    """One row's full replacement coding. ``item_id`` is the qualified id
    (``t3_<id>``/``t1_<id>``, see ``core/item_types.py``) as returned by
    ``GET /api/coding/{ref}/rows``. An empty ``entries`` list clears every
    code from that row -- the row is not left untouched.
    """

    item_id: str = Field(min_length=1)
    entries: list[CodingEntryIn] = Field(default_factory=list)


class CodebookCodeIn(_StrippingModel):
    """One structured code, as saved from the codebook editor.

    Identity is explicit, not inferred: a code being kept/edited/moved
    carries its existing ``code_uid``; a code the editor just created
    carries ``is_new=True`` instead (and no ``code_uid``) -- the service
    layer mints a fresh uid for it, but ONLY when told to. A code with
    neither is rejected rather than silently re-identified, which would
    otherwise show up as a spurious delete+add in the version history
    diff. ``family_uid``/``family_is_new`` follow the same rule for the
    code's family.
    """

    # Identity is validated in `codebook_service._resolve_code_rows`, not
    # here -- a Pydantic field_validator's `info.data` only sees fields
    # validated BEFORE it in declaration order, which makes a robust
    # "code_uid required unless is_new" check awkward to express as a
    # field validator (and a model_validator would just duplicate the
    # service-layer check this schema's one real caller already runs).
    code_uid: Optional[str] = None
    is_new: bool = False
    family_uid: Optional[str] = None
    family_is_new: bool = False
    family_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    body: str = ""
    definition: Optional[str] = None
    inclusion: Optional[str] = None
    exclusion: Optional[str] = None
    keywords: Optional[str] = None
    example: Optional[str] = None


class SaveCodebookRequest(_StrippingModel):
    """Payload for ``PUT /api/codebook/{ref}``. ``assist_runs`` is the
    same C2 provenance channel as ``ManualCodebookRequest`` -- Refine
    mode is an equally AI-assisted path as New."""

    codes: list[CodebookCodeIn] = Field(min_length=1)
    display_name: Optional[str] = None
    assist_runs: list[AssistRunIn] = Field(default_factory=list)


class ImportCodebookRequest(_StrippingModel):
    """Payload for ``POST /api/codebook/{ref}/import`` -- pasted/uploaded
    markdown, parsed into structured rows (see
    ``core/codebook_render.py::parse_markdown_to_codes``).
    """

    markdown: str = Field(min_length=1)


class SaveCodingRevisionRequest(_StrippingModel):
    """Payload for ``PUT /api/coding/{ref}/revision`` -- one unified save
    for a coding artifact's editing session: an updated codebook
    snapshot, updated row coding, or both together, committed as at most
    one new ``artifact_versions`` row (see
    ``coding_service.save_coding_revision``).

    No ``model``/``job_id`` here any more -- that used to be the one
    place an AI assist leaked onto an ``origin=edited`` version's
    ``model`` field, which is exactly what the C2 design forbids (see
    ``versioning_models.ArtifactAssist``). ``assist_runs`` (see
    ``AssistRunIn``) is the replacement channel, and each accepted
    entry's own attribution travels on it via
    ``CodingEntryIn.coder``/``assist_job_id``.

    At least one of ``codes``/``rows`` must be given -- a request with
    neither has nothing to save.
    """

    codes: Optional[list[CodebookCodeIn]] = None
    rows: Optional[list[CodingRowUpdate]] = None
    assist_runs: list[AssistRunIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _at_least_one(self):
        if not self.codes and not self.rows:
            raise ValueError("At least one of codes/rows is required")
        return self


class UpdateCodingMetadataRequest(_StrippingModel):
    """Payload for ``PATCH /api/coding/{ref}``."""

    display_name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None


class DuplicateCodingRequest(_StrippingModel):
    """Payload for ``POST /api/coding/{ref}/duplicate``. ``from_version_no``
    forks from that point in the artifact's history instead of head --
    the non-destructive replacement for the old forward-commit revert.
    """

    display_name: str = Field(min_length=1)
    from_version_no: Optional[int] = Field(default=None, ge=1)


class DuplicateCodebookRequest(_StrippingModel):
    """Payload for ``POST /api/codebook/{ref}/duplicate``. Same shape and
    same ``from_version_no`` semantics as ``DuplicateCodingRequest``.
    """

    display_name: str = Field(min_length=1)
    from_version_no: Optional[int] = Field(default=None, ge=1)


class RecodeItemsRequest(_StrippingModel):
    """Payload for ``POST /api/coding/{ref}/recode`` -- re-run the AI
    classifier over a chosen subset of a coding artifact's own rows with
    a caller-chosen model, replacing exactly those rows' coding.
    """

    api_key: str = Field(min_length=1)
    item_ids: list[str] = Field(min_length=1)
    model: str = Field(min_length=1, description="OpenRouter model slug")
    methodology: Optional[str] = None


class ManualCodingRequest(_StrippingModel):
    """Payload for ``POST /api/coding/manual`` -- start a coding artifact
    by hand: copy the chosen rows in and snapshot the codebook, but code
    nothing. Carries no ``api_key``/``model``/``methodology`` because it
    calls no model.

    JSON rather than ``as_form`` because it can carry explicit row-id
    lists (same reasoning as ManualFilterRequest).
    """

    database: str = Field(pattern=_SCHEMA_PATTERN)
    codebook: str = Field(
        min_length=1,
        description="Either a numeric File id or a proj_<hex> schema name",
    )
    report_name: str = Field(min_length=1, description="Display name for the coding output")
    description: Optional[str] = None
    project_id: int = Field(description="Owning project -- every artifact belongs to one")
    sample_percentage: float = Field(default=100.0, ge=1.0, le=100.0)
    content_scope: ContentScope = _content_scope_field()
    # Explicit ids win when either list is non-empty; otherwise the rows
    # are sampled by sample_percentage within content_scope. Both empty is
    # the ordinary case (sample), so neither is required.
    post_ids: list[str] = Field(default_factory=list)
    comment_ids: list[str] = Field(default_factory=list)

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        return _strip_db_suffix_value(value)

    @field_validator("codebook")
    @classmethod
    def _validate_codebook_ref(cls, value: str) -> str:
        return _validate_codebook_ref_value(value)


# ---------------------------------------------------------------------------
# PostContents
# ---------------------------------------------------------------------------


class PostContentsRequest(_StrippingModel):
    """Payload for ``POST /api/post-contents/``.

    Was a bare ``dict`` body -- moved to a real schema so this route
    boundary follows the same "no bare dict at a route boundary" rule as
    the rest of the API. ``post_ids`` may be a mix of qualified ids
    (``t3_<id>``/``t1_<id>``, see ``backend/app/core/item_types.py``) and
    legacy unprefixed ids, since coding artifacts saved before item
    types existed only ever contain the latter.
    """

    schema_: str = Field(alias="schema", min_length=1)
    post_ids: list[str] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Data (raw_data/filtered_data) row edits + restore
# ---------------------------------------------------------------------------


class DeleteRowsRequest(_StrippingModel):
    """Payload for ``POST /api/delete-rows/``. Replaces the old
    single-row, ``Form``-encoded ``/delete-row/`` -- a JSON body so a
    whole selection closes in one call (one version), not one request
    per row.
    """

    schema_name: str = Field(min_length=1)
    table: str = Field(min_length=1)
    row_ids: list[str] = Field(min_length=1)


class DuplicateDataRequest(_StrippingModel):
    """Payload for ``POST /api/data/{ref}/duplicate``. Same shape and
    same ``from_version_no`` semantics as ``DuplicateCodingRequest``/
    ``DuplicateCodebookRequest`` -- the restore path for
    ``raw_data``/``filtered_data`` files.
    """

    display_name: str = Field(min_length=1)
    from_version_no: Optional[int] = Field(default=None, ge=1)

    model_config = {"populate_by_name": True}


class AiModelPricing(BaseModel):
    inputUsdPerMillion: float
    outputUsdPerMillion: float


class AiModelOut(BaseModel):
    value: str
    label: str
    paid: bool
    pricing: Optional[AiModelPricing] = None


class StarQuoteRequest(BaseModel):
    starred: bool = Field(True, description="True to star, False to unstar")


class UpdateQuoteNotesRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Note text attached to the quote")


class ForgotPasswordRequest(_StrippingModel):
    email: str = Field(..., min_length=1)


class ResetPasswordRequest(BaseModel):
    # Plain BaseModel: a password must never be whitespace-stripped.
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    message: str
