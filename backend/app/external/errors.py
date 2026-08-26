"""Shared error-classification helpers for external (LLM/HTTP) API calls.

``extract_http_error_code`` was duplicated near-identically in
``backend/scripts/filter_db.py`` and ``backend/scripts/tag_expansion.py``;
this is the one copy going forward.
"""

import re

_ERROR_CODE_RE = re.compile(r"Error code:\s*(\d{3})")


class ExternalServiceError(Exception):
    """Raised by :mod:`backend.app.external.openrouter_client` on a failed call."""

    def __init__(self, message: str, *, code: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def extract_http_error_code(error: Exception) -> int:
    """Best-effort HTTP status code from an OpenAI/OpenRouter SDK exception."""
    error_str = str(error)
    match = _ERROR_CODE_RE.search(error_str)
    if match:
        return int(match.group(1))
    if hasattr(error, "status_code"):
        return int(getattr(error, "status_code", 0) or 0)
    return 0


# Codes that mean the *request itself* is permanently broken (bad key, no
# credits, flagged content, an invalid model slug, a malformed request) --
# retrying sends the exact same doomed request again, so these should fail
# immediately instead of burning through backoff and more attempts.
# Matches ``backend/scripts/openrouter_http.py``'s own permanent-vs-transient
# split of ``OPENROUTER_CLIENT_ERROR_CODES``: 408/429/502/503 (plus network
# errors and empty completions, which carry no code at all) are transient
# and stay retryable by default.
NON_RETRYABLE_HTTP_CODES = frozenset({400, 401, 402, 403, 404})


def is_retryable_error(error: Exception) -> bool:
    """Whether ``error`` (as raised by the OpenRouter SDK) is worth
    retrying -- ``False`` for a permanent, request-is-broken error (see
    :data:`NON_RETRYABLE_HTTP_CODES`), ``True`` for everything else
    (408/429/502/503, network errors, empty completions with no code at
    all), which are presumed transient.
    """
    return extract_http_error_code(error) not in NON_RETRYABLE_HTTP_CODES
