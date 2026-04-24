"""
Expand user filter tags via OpenRouter for keyword pre-filtering on post/comment text.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import OpenAI

from backend.scripts.openrouter_http import openrouter_user_message

OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2
MAX_EXPANDED_TERMS = 50
MAX_TERM_CHARS = 80

TAG_EXPANSION_SYSTEM = """You expand seed tags into search terms for substring matching in social-style posts and comments (e.g. Reddit).

Return exactly one JSON object with keys: original_tags (array of strings), expanded_terms (array of strings), notes (string, may be empty). No markdown or code fences.

Content rules:
- Echo every seed in original_tags (trimmed). expanded_terms must include every seed verbatim (trimmed) plus 8–28 additional terms.
- Additional terms: synonyms, colloquial phrases, common abbreviations/clinical shorthand when tied to the topic (e.g. near anxiety: worry, nervous, panic attack, GAD, intrusive thoughts, on edge, racing thoughts), and close hyponyms—forms users might actually type.
- Each term: 1–4 words, letters/digits/apostrophes/hyphens only; no hashtags, URLs, bullets, or full sentences.
- Every non-seed term must clearly relate to at least one seed. Prefer recall, but drop unrelated tangents.
- Do not add generic platform or meta words as standalone terms: post, thread, comment, update, karma, OP, mod, subreddit, sub, reddit, upvote, award, discussion, community, people, someone, anyone, thing, stuff, lol, tbh, imo—unless embedded inside a clearly on-topic multi-word phrase that is not just those words (e.g. "social anxiety" is fine; "social" alone is not).
- Avoid duplicate or near-duplicate strings (case-insensitive).

Quality bar: a researcher reading expanded_terms should agree each term plausibly co-occurs with the topic in authentic posts."""


class TagExpansionError(Exception):
    def __init__(self, message: str, code: int = 0):
        self.code = code
        super().__init__(message)


def _extract_error_code(error: Exception) -> int:
    error_str = str(error)
    match = re.search(r"Error code:\s*(\d{3})", error_str)
    if match:
        return int(match.group(1))
    if hasattr(error, "status_code"):
        return int(getattr(error, "status_code", 0) or 0)
    return 0


def parse_filter_tags_input(raw: str | None) -> list[str]:
    """Split comma/newline-separated tags; trim; drop empties."""
    if not raw or not str(raw).strip():
        return []
    parts = re.split(r"[\n,]+", str(raw))
    return [p.strip() for p in parts if p.strip()]


def _normalize_term(s: str) -> str:
    t = " ".join(s.split())
    return t[:MAX_TERM_CHARS] if len(t) > MAX_TERM_CHARS else t


def normalize_and_cap_terms(terms: list[str], cap: int = MAX_EXPANDED_TERMS) -> list[str]:
    """Lowercase dedupe, drop too-short tokens, cap length."""
    seen: set[str] = set()
    out: list[str] = []
    for x in terms:
        if not x or not isinstance(x, str):
            continue
        n = _normalize_term(x.strip())
        if len(n) < 2:
            continue
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
        if len(out) >= cap:
            break
    return out


def _strip_json_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        content = "\n".join(lines).strip()
    return content


def _parse_expansion_json(content: str) -> dict[str, Any]:
    raw = _strip_json_fences(content)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise TagExpansionError(f"Tag expansion returned invalid JSON: {e}", code=502) from e
    if not isinstance(obj, dict):
        raise TagExpansionError("Tag expansion JSON must be an object", code=502)
    return obj


def expand_tags_via_openrouter(
    user_tags: list[str],
    api_key: str,
    model: str,
) -> tuple[list[str], list[str]]:
    """
    Call OpenRouter once with all seed tags.

    `api_key` must be the end-user OpenRouter key (e.g. from the app navbar); the API route passes
    the same key used for AI filtering. Do not substitute server environment variables here.

    Returns:
        (original_tags_normalized, expanded_terms_capped)
    """
    if not user_tags:
        return [], []
    if not api_key or not api_key.strip():
        raise TagExpansionError("API key is required for tag expansion", code=401)

    chosen = (model or "").strip() or DEFAULT_MODEL
    user_payload = json.dumps(
        {"seed_tags": user_tags},
        ensure_ascii=False,
    )
    user_message = (
        f"Expand these seed tags for text search in social posts and comments:\n{user_payload}\n\n"
        "Return only the JSON object described in your instructions."
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = OpenAI(api_key=api_key, base_url=OPENROUTER_URL)
            try:
                response = client.chat.completions.create(
                    model=chosen,
                    messages=[
                        {"role": "system", "content": TAG_EXPANSION_SYSTEM},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                    timeout=120,
                    response_format={"type": "json_object"},
                    extra_body={"transforms": ["middle-out"]},
                )
            except Exception:
                response = client.chat.completions.create(
                    model=chosen,
                    messages=[
                        {"role": "system", "content": TAG_EXPANSION_SYSTEM},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                    timeout=120,
                    extra_body={"transforms": ["middle-out"]},
                )
            if not response.choices or not response.choices[0].message:
                raise ValueError("Empty response from model")
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty message content from model")
            data = _parse_expansion_json(content)
            orig = data.get("original_tags") or user_tags
            if not isinstance(orig, list):
                orig = user_tags
            orig_norm = normalize_and_cap_terms([str(x) for x in orig], cap=20)
            expanded_raw = data.get("expanded_terms")
            if not isinstance(expanded_raw, list):
                expanded_raw = []
            merged = normalize_and_cap_terms(
                [str(x) for x in expanded_raw] + user_tags,
                cap=MAX_EXPANDED_TERMS,
            )
            if not merged:
                merged = normalize_and_cap_terms(user_tags, cap=MAX_EXPANDED_TERMS)
            return orig_norm or normalize_and_cap_terms(user_tags, cap=20), merged
        except TagExpansionError:
            raise
        except Exception as e:
            last_error = e
            if attempt == MAX_RETRIES:
                code = _extract_error_code(e)
                msg = (
                    openrouter_user_message(code, chosen)
                    if code
                    else str(e)
                )
                raise TagExpansionError(msg, code=code or 502) from e
            time.sleep(INITIAL_RETRY_DELAY * (2 ** (attempt - 1)))

    raise TagExpansionError(str(last_error or "Unknown error"), code=502)


def submission_text_tag_predicate_sql(terms: list[str]) -> tuple[str, dict[str, Any]]:
    """SQL fragment AND (... OR position(lower(:tx) in lower(title || selftext)) ...) and bind dict."""
    if not terms:
        return "", {}
    parts: list[str] = []
    bind: dict[str, Any] = {}
    for i, t in enumerate(terms):
        key = f"tag_sub_{i}"
        parts.append(
            f"position(lower(:{key}) in lower(coalesce(title, '') || ' ' || coalesce(selftext, ''))) > 0"
        )
        bind[key] = t.lower()
    return " AND (" + " OR ".join(parts) + ")", bind


def comment_body_tag_predicate_sql(terms: list[str]) -> tuple[str, dict[str, Any]]:
    if not terms:
        return "", {}
    parts = []
    bind: dict[str, Any] = {}
    for i, t in enumerate(terms):
        key = f"tag_com_{i}"
        parts.append(f"position(lower(:{key}) in lower(coalesce(body, ''))) > 0")
        bind[key] = t.lower()
    return " AND (" + " OR ".join(parts) + ")", bind
