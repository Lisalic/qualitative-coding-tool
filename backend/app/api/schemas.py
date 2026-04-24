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
from typing import Any, Optional, Type, TypeVar

from fastapi import Form
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError, field_validator

T = TypeVar("T", bound=BaseModel)


_SCHEMA_PATTERN = r"^proj_[A-Za-z0-9_]+$"


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
    """Shared config: whitespace is stripped, unknown fields are rejected."""

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
