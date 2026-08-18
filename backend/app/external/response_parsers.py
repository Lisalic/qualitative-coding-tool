"""Shared response-parsing primitives.

Only the primitive that was genuinely duplicated (markdown-fence
stripping, in ``backend/scripts/filter_db.py`` and
``backend/scripts/tag_expansion.py``) lives here. The 4 scripts' actual
response *parsing* (free-form text, the POST_ID/CODE/EVIDENCE DSL,
``ast.literal_eval`` array, JSON) stays script-specific -- they're
genuinely different output contracts.
"""

import json
from typing import Any


def strip_markdown_fences(content: str) -> str:
    """Remove leading/trailing ``` fence lines from an LLM response, if present."""
    content = (content or "").strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        content = "\n".join(lines).strip()
    return content


def parse_json_object(content: str, *, error_cls: type[Exception] = ValueError) -> dict[str, Any]:
    """Strip fences, parse JSON, and require the result to be an object.

    Raises ``error_cls`` (default ``ValueError``) on invalid JSON or a
    non-dict top-level value.
    """
    raw = strip_markdown_fences(content)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise error_cls(f"Response was not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise error_cls("Response JSON must be an object")
    return obj
