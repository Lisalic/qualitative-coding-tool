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
