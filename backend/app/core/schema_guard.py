"""Schema-name normalization/validation.

Relocates the logic that used to live only in ``backend/app/api/utils.py``
(kept there as a re-export for existing importers -- see that module).
Every dynamic-SQL call site that touches a schema name should go through
``require_valid_schema`` rather than reimplementing its own regex/prefix
check, which is how the unvalidated ``get_post_contents`` gap happened.
"""

import re

from backend.app.core.exceptions import ValidationAppError

ALLOWED_SCHEMA_PREFIXES: tuple[str, ...] = ("proj_", "cmp_", "sum_")

_PATTERN_CACHE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _pattern_for_prefixes(prefixes: tuple[str, ...]) -> re.Pattern[str]:
    """``^(?:prefix1|prefix2|...)[A-Za-z0-9_]+$`` -- at least one char after the prefix.

    Matches the original ``is_proj_schema``'s ``^proj_[A-Za-z0-9_]+$`` exactly
    for the single-prefix case (verified: rejects a bare ``"proj_"``).
    """
    pattern = _PATTERN_CACHE.get(prefixes)
    if pattern is None:
        alternation = "|".join(re.escape(p) for p in prefixes)
        pattern = re.compile(rf"^(?:{alternation})[A-Za-z0-9_]+$")
        _PATTERN_CACHE[prefixes] = pattern
    return pattern


def normalize_schema(raw: str | None) -> str:
    """Strip whitespace and a trailing ``.db`` from a schema name.

    Returns an empty string for ``None`` so callers can use the usual
    ``if not schema`` check before the structural prefix test.
    """
    if raw is None:
        return ""
    value = raw.strip()
    if value.endswith(".db"):
        value = value[:-3]
    return value


def is_valid_artifact_schema(
    name: str, *, allowed_prefixes: tuple[str, ...] = ALLOWED_SCHEMA_PREFIXES
) -> bool:
    """True when ``name`` is a well-formed identifier with an allowed prefix."""
    if not name:
        return False
    return bool(_pattern_for_prefixes(allowed_prefixes).match(name))


def is_proj_schema(name: str) -> bool:
    """True when ``name`` matches the ``proj_<hex>`` schema convention.

    Kept as a narrower alias of :func:`is_valid_artifact_schema` for
    call sites that specifically only accept ``proj_`` (raw/filtered data),
    matching the original helper in ``api/utils.py``.
    """
    return is_valid_artifact_schema(name, allowed_prefixes=("proj_",))


def require_valid_schema(
    raw: str | None,
    *,
    field_name: str = "schema",
    allowed_prefixes: tuple[str, ...] = ("proj_",),
) -> str:
    """Normalize + validate; raises ``ValidationAppError`` (400) if invalid."""
    value = normalize_schema(raw)
    if not is_valid_artifact_schema(value, allowed_prefixes=allowed_prefixes):
        raise ValidationAppError(f"Invalid {field_name} name")
    return value
