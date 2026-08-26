"""Pydantic request/response contracts for the three core tool-panel flows.

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
from typing import Any, Literal, Optional, Type, TypeVar

from fastapi import Form
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError, field_validator

T = TypeVar("T", bound=BaseModel)


_SCHEMA_PATTERN = r"^proj_[A-Za-z0-9_]+$"

ContentScope = Literal["both", "posts", "comments"]


def _content_scope_field() -> Any:
    """Which of a source file's submissions/comments tables an AI tool
    should sample from. Shared across Filter/Generate/Apply so the three
    form builders (buildFilterDataForm/buildGenerateCodebookForm/
    buildApplyCodebookForm in apiContracts.js) send the same field name.
    Defaults to "both" -- today's behavior for every one of these tools,
    unchanged for any existing caller that doesn't send this field.
    """
    return Field(
        default="both",
        description="Which content types to sample: 'both', 'posts', or 'comments'",
    )


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
# FilterData
# ---------------------------------------------------------------------------


class FilterDataRequest(_StrippingModel):
    """Payload for ``POST /api/filter-data/``.

    The frontend builder is ``buildFilterDataForm`` in
    ``frontend/src/lib/apiContracts.js``.
    """

    api_key: str = Field(min_length=1, description="OpenRouter API key from the client")
    database: str = Field(
        pattern=_SCHEMA_PATTERN,
        description="Source Postgres schema (proj_<hex>)",
    )
    name: str = Field(min_length=1, description="Display name for the new filtered file")
    model: str = Field(min_length=1, description="OpenRouter model slug")
    project_id: Optional[int] = Field(
        default=None, description="Optional project to attach the resulting file to"
    )
    prompt: Optional[str] = Field(
        default=None, description="Filter prompt; skipped when only tags are used"
    )
    description: Optional[str] = Field(default=None)
    min_words: int = Field(default=0, ge=0, description="Minimum word count predicate")
    sample_percentage: float = Field(
        default=100.0,
        ge=1.0,
        le=100.0,
        description="Random-sample percentage per table before AI",
    )
    filter_tags: Optional[str] = Field(
        default=None,
        description="Comma-separated keywords to pre-filter with tag expansion",
    )
    content_scope: ContentScope = _content_scope_field()

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.endswith(".db"):
            value = value[:-3]
        return value


class FilterDataFileInfo(BaseModel):
    id: str
    schema_name: str
    filename: str


class FilterDataTagInfo(BaseModel):
    original_tags: list[str]
    expanded_terms: list[str]


class FilterDataResponse(BaseModel):
    message: str
    submissions_length: int
    comments_length: int
    posts_filtered_count: int
    comments_filtered_count: int
    file: Optional[FilterDataFileInfo] = None
    tag_filter: Optional[FilterDataTagInfo] = None
    partial: bool = False
    batches_processed: Optional[dict[str, int]] = None
    batches_total: Optional[dict[str, int]] = None
    orphaned_comments: int = 0


# ---------------------------------------------------------------------------
# GenerateCodebook
# ---------------------------------------------------------------------------


class GenerateCodebookRequest(_StrippingModel):
    """Payload for ``POST /api/generate-codebook/``."""

    api_key: str = Field(min_length=1)
    database: str = Field(pattern=_SCHEMA_PATTERN)
    name: str = Field(min_length=1, description="Display name for the generated codebook")
    model: Optional[str] = Field(
        default=None, description="OpenRouter model slug; falls back to server default"
    )
    prompt: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    project_id: Optional[int] = Field(default=None)
    sample_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    content_scope: ContentScope = _content_scope_field()

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.endswith(".db"):
            value = value[:-3]
        return value


class GenerateCodebookFileInfo(BaseModel):
    id: str
    schema_name: str
    filename: str
    description: Optional[str] = None


class GenerateCodebookResponse(BaseModel):
    codebook: str
    file: GenerateCodebookFileInfo


# ---------------------------------------------------------------------------
# CompareCodebooks
# ---------------------------------------------------------------------------


class CompareCodebooksRequest(_StrippingModel):
    """Payload for ``POST /api/compare-codebooks/``."""

    codebook_a: str = Field(pattern=_SCHEMA_PATTERN)
    codebook_b: str = Field(pattern=_SCHEMA_PATTERN)
    api_key: str = Field(min_length=1)
    name: str = Field(min_length=1, description="Display name for the comparison")
    model: Optional[str] = Field(default=None)
    prompt: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    project_id: Optional[int] = Field(default=None)


# ---------------------------------------------------------------------------
# ApplyCodebook
# ---------------------------------------------------------------------------


class ApplyCodebookRequest(_StrippingModel):
    """Payload for ``POST /api/apply-codebook/``."""

    api_key: str = Field(min_length=1)
    database: str = Field(pattern=_SCHEMA_PATTERN)
    codebook: str = Field(
        min_length=1,
        description="Either a numeric File id or a proj_<hex> schema name",
    )
    report_name: str = Field(min_length=1, description="Display name for the coding output")
    methodology: Optional[str] = Field(
        default=None, description="Optional instructions steering the classifier"
    )
    model: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    project_id: Optional[int] = Field(default=None)
    sample_percentage: float = Field(default=100.0, ge=1.0, le=100.0)
    content_scope: ContentScope = _content_scope_field()

    @field_validator("database", mode="before")
    @classmethod
    def _strip_db_suffix(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.endswith(".db"):
            value = value[:-3]
        return value

    @field_validator("codebook")
    @classmethod
    def _validate_codebook_ref(cls, value: str) -> str:
        raw = value.strip()
        if not raw:
            raise ValueError("codebook must not be empty")
        if raw.startswith("proj_"):
            # structural check mirrors _SCHEMA_PATTERN
            import re as _re

            if not _re.match(_SCHEMA_PATTERN, raw):
                raise ValueError("codebook schema must match proj_<hex>")
            return raw
        # otherwise it must parse as int (File id)
        try:
            int(raw)
        except ValueError as exc:
            raise ValueError(
                "codebook must be a numeric File id or a proj_<hex> schema name"
            ) from exc
        return raw


class ApplyCodebookResponse(BaseModel):
    classification_output: str
    file: Optional[GenerateCodebookFileInfo] = None


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
# recode routes in coding_routes.py, not Apply Codebook's kickoff (that's
# still ApplyCodebookRequest above). Sent as JSON bodies, not
# multipart/form-data (unlike the ``as_form`` models above), since a
# per-row list of code/evidence/notes entries doesn't map onto flat form
# fields the way FilterData/GenerateCodebook/ApplyCodebook's scalar
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
    """

    code: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    notes: Optional[str] = None

    @field_validator("end_offset")
    @classmethod
    def _end_after_start(cls, end_offset: int, info) -> int:
        start_offset = info.data.get("start_offset")
        if start_offset is not None and end_offset <= start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return end_offset


class CodingRowUpdate(_StrippingModel):
    """One row's full replacement coding. ``item_id`` is the qualified id
    (``t3_<id>``/``t1_<id>``, see ``core/item_types.py``) as returned by
    ``GET /api/coding/{ref}/rows``. An empty ``entries`` list clears every
    code from that row -- the row is not left untouched.
    """

    item_id: str = Field(min_length=1)
    entries: list[CodingEntryIn] = Field(default_factory=list)


class SaveCodingRowsRequest(_StrippingModel):
    """Payload for ``PUT /api/coding/{ref}/rows``."""

    rows: list[CodingRowUpdate] = Field(min_length=1)


class SaveCodingCodebookRequest(_StrippingModel):
    """Payload for ``PUT /api/coding/{ref}/codebook``."""

    content: str = Field(min_length=1)


class UpdateCodingMetadataRequest(_StrippingModel):
    """Payload for ``PATCH /api/coding/{ref}``."""

    display_name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None


class DuplicateCodingRequest(_StrippingModel):
    """Payload for ``POST /api/coding/{ref}/duplicate``."""

    display_name: str = Field(min_length=1)


class RecodeItemsRequest(_StrippingModel):
    """Payload for ``POST /api/coding/{ref}/recode`` -- re-run the AI
    classifier over a chosen subset of a coding artifact's own rows with
    a caller-chosen model, replacing exactly those rows' coding.
    """

    api_key: str = Field(min_length=1)
    item_ids: list[str] = Field(min_length=1)
    model: Optional[str] = None
    methodology: Optional[str] = None


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

    model_config = {"populate_by_name": True}


class AiModelPricing(BaseModel):
    inputUsdPerMillion: float
    outputUsdPerMillion: float


class AiModelOut(BaseModel):
    value: str
    label: str
    paid: bool
    pricing: Optional[AiModelPricing] = None
