"""Codebook rows <-> markdown/JSON -- the wire/prompt formats for a
codebook that now lives as ``codebook_codes`` rows.

``parse_json_to_codes`` is the generator importer: the LLM's
``{"codes": [...]}`` object -> rows, filling ``definition``/``inclusion``/
``exclusion``/``keywords``/``example`` and reconstructing a labeled
``body`` so apply/compare still receive markdown.

``parse_markdown_to_codes`` is the paste/upload importer: it wraps
``backend/scripts/display_codebook.py::parse_codebook_to_json`` --
that module's parsing contract (the ``### Code Family:``/``#### Code
Name:`` markers, orphan-content-dropped, duplicate-family-names-not-merged
behavior, all pinned by ``tests/backend/test_display_codebook.py``) is
unchanged; this adds identity on top of it and splits labeled field
lines out of each code's free-text body.

``render_codes_to_markdown`` is the exporter: rows -> labeled markdown,
used wherever a codebook needs to be handed to an LLM (the apply
prompt, the compare prompt) or shown as read-only text. It groups by
``family_uid``, deliberately never by ``family_name`` -- two families
sharing a name must stay two separate blocks, matching the parser's own
non-merging behavior (see ``CodebookCode``'s docstring in
``versioning_models.py``). It always emits from the structured columns;
unlabeled leftover prose is stored as ``definition``, not as a second
display path.

Round-trip is a fixed point for any codebook this module produced itself
(rows -> markdown -> rows reproduces the same rows, modulo re-minted
uids on the second parse -- callers doing a real re-import pass an
``existing`` set to preserve identity instead).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Sequence, TypedDict

from backend.app.external.response_parsers import parse_json_object
from backend.scripts.display_codebook import parse_codebook_to_json

# Render order / canonical labels. Aliases on the left of _LABEL_TO_FIELD
# are accepted on parse so "Inclusion:" and "Inclusion Criteria:" both land
# in the same column.
_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("definition", "Definition"),
    ("inclusion", "Inclusion Criteria"),
    ("exclusion", "Exclusion Criteria"),
    ("keywords", "Key Words"),
    ("example", "Example"),
)
_LABEL_TO_FIELD = {
    "definition": "definition",
    "inclusion criteria": "inclusion",
    "inclusion": "inclusion",
    "exclusion criteria": "exclusion",
    "exclusion": "exclusion",
    "key words": "keywords",
    "keywords": "keywords",
    "example": "example",
}
_LABEL_RE = re.compile(
    r"^\*{0,2}_{0,2}\s*(definition|inclusion criteria|inclusion|exclusion criteria|exclusion|key words|keywords|example)\s*\*{0,2}_{0,2}\s*:\s*\*{0,2}_{0,2}\s*(.*)$",
    re.IGNORECASE,
)
_LEADING_SELF_LABEL = {
    "definition": re.compile(r"^\*{0,2}definition\*{0,2}\s*:\s*", re.IGNORECASE),
    "inclusion": re.compile(r"^\*{0,2}inclusion(?:\s+criteria)?\*{0,2}\s*:\s*", re.IGNORECASE),
    "exclusion": re.compile(r"^\*{0,2}exclusion(?:\s+criteria)?\*{0,2}\s*:\s*", re.IGNORECASE),
    "keywords": re.compile(r"^\*{0,2}key\s*words\*{0,2}\s*:\s*", re.IGNORECASE),
    "example": re.compile(r"^\*{0,2}example\*{0,2}\s*:\s*", re.IGNORECASE),
}


class CodeRow(TypedDict):
    code_uid: str
    family_uid: str
    family_name: str
    name: str
    body: str
    definition: str | None
    inclusion: str | None
    exclusion: str | None
    keywords: str | None
    example: str | None
    position: int


def _new_code_row(
    *,
    code_uid: str,
    family_uid: str,
    family_name: str,
    name: str,
    body: str,
    position: int,
    definition: str | None = None,
    inclusion: str | None = None,
    exclusion: str | None = None,
    keywords: str | None = None,
    example: str | None = None,
) -> CodeRow:
    return CodeRow(
        code_uid=code_uid,
        family_uid=family_uid,
        family_name=family_name,
        name=name,
        body=body,
        definition=definition,
        inclusion=inclusion,
        exclusion=exclusion,
        keywords=keywords,
        example=example,
        position=position,
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _body_from_fields(
    *,
    definition: str | None = None,
    inclusion: str | None = None,
    exclusion: str | None = None,
    keywords: str | None = None,
    example: str | None = None,
) -> str:
    values = {
        "definition": definition,
        "inclusion": inclusion,
        "exclusion": exclusion,
        "keywords": keywords,
        "example": example,
    }
    chunks: list[str] = []
    for key, label in _FIELD_LABELS:
        value = _optional_text(values[key])
        if value:
            chunks.append(f"{label}: {value}")
    return "\n".join(chunks)


def _unwrap_wrapped_definition(content: str) -> str:
    """Undo a previous pass that stored a still-labeled block as one definition."""
    text = (content or "").strip()
    if not text.lower().startswith("definition:"):
        return text
    rest = text.split(":", 1)[1].lstrip()
    first = rest.split("\n", 1)[0].strip()
    match = _LABEL_RE.match(first)
    if match and _LABEL_TO_FIELD[match.group(1).lower()] == "definition":
        return rest
    return text


def materialize_fields_from_body(content: str) -> dict[str, str | None]:
    """Split labeled lines out of ``content``; unlabeled prose becomes
    ``definition``. Always returns a reconstructed ``body`` plus the five
    structured fields -- there is no body-only leftover path.
    """
    fields = _split_labeled_fields(_unwrap_wrapped_definition(content))
    if not any(fields.values()):
        leftover = (content or "").strip()
        if leftover:
            fields["definition"] = leftover
    fields["body"] = _body_from_fields(
        definition=fields["definition"],
        inclusion=fields["inclusion"],
        exclusion=fields["exclusion"],
        keywords=fields["keywords"],
        example=fields["example"],
    )
    return fields


def _split_labeled_fields(content: str) -> dict[str, str | None]:
    """Pull labeled lines out of a code's markdown body.

    Unlabeled prose with no field labels at all leaves every field None
    (``materialize_fields_from_body`` then stores that prose as
    ``definition``). Continuation lines after a label append to that field.
    """
    empty = {key: None for key, _ in _FIELD_LABELS}
    if not (content or "").strip():
        return empty

    fields: dict[str, str | None] = dict(empty)
    current: str | None = None
    found_any = False
    for raw_line in content.split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            continue
        match = _LABEL_RE.match(stripped)
        if match:
            found_any = True
            current = _LABEL_TO_FIELD[match.group(1).lower()]
            rest = match.group(2).strip()
            fields[current] = rest
            continue
        if current is not None:
            prev = fields[current] or ""
            fields[current] = f"{prev}\n{stripped}".strip() if prev else stripped

    if not found_any:
        return empty
    cleaned: dict[str, str | None] = {}
    for key, value in fields.items():
        text = _optional_text(value)
        if text:
            text = _LEADING_SELF_LABEL[key].sub("", text, count=1).strip() or None
        cleaned[key] = text
    return cleaned


def _identity_indexes(
    existing: Sequence[CodeRow],
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    existing_family_uid_by_name: dict[str, str] = {}
    existing_code_uid_by_key: dict[tuple[str, str], str] = {}
    for row in existing:
        existing_family_uid_by_name.setdefault(row["family_name"], row["family_uid"])
        existing_code_uid_by_key[(row["family_name"], row["name"])] = row["code_uid"]
    return existing_family_uid_by_name, existing_code_uid_by_key


def parse_json_to_codes(raw: str, *, existing: Sequence[CodeRow] = ()) -> list[CodeRow]:
    """Parse the generator's ``{"codes": [...]}`` JSON into ``CodeRow`` dicts.

    Codes missing ``family`` or ``name`` are dropped. Consecutive entries
    sharing a family name share a ``family_uid``; a later repeat after a
    different family is a new family (same non-merge rule as markdown).
    ``existing`` preserves identity by ``(family_name, name)`` the same
    way ``parse_markdown_to_codes`` does.
    """
    obj = parse_json_object(raw, error_cls=ValueError)
    codes_raw = obj.get("codes")
    if not isinstance(codes_raw, list):
        raise ValueError("Response JSON must have a 'codes' array")

    existing_family_uid_by_name, existing_code_uid_by_key = _identity_indexes(existing)

    rows: list[CodeRow] = []
    position = 0
    current_family_name: str | None = None
    current_family_uid: str | None = None
    for item in codes_raw:
        if not isinstance(item, dict):
            continue
        family_name = str(item.get("family") or "").strip()
        name = str(item.get("name") or "").strip()
        if not family_name or not name:
            continue
        if family_name != current_family_name:
            current_family_name = family_name
            current_family_uid = existing_family_uid_by_name.get(family_name) or uuid.uuid4().hex
        definition = _optional_text(item.get("definition"))
        inclusion = _optional_text(item.get("inclusion"))
        exclusion = _optional_text(item.get("exclusion"))
        keywords = _optional_text(item.get("keywords"))
        example = _optional_text(item.get("example"))
        rows.append(
            _new_code_row(
                code_uid=existing_code_uid_by_key.get((family_name, name)) or uuid.uuid4().hex,
                family_uid=current_family_uid or uuid.uuid4().hex,
                family_name=family_name,
                name=name,
                body=_body_from_fields(
                    definition=definition,
                    inclusion=inclusion,
                    exclusion=exclusion,
                    keywords=keywords,
                    example=example,
                ),
                position=position,
                definition=definition,
                inclusion=inclusion,
                exclusion=exclusion,
                keywords=keywords,
                example=example,
            )
        )
        position += 1
    return rows


def parse_markdown_to_codes(raw: str, *, existing: Sequence[CodeRow] = ()) -> list[CodeRow]:
    """Parse ``raw`` codebook markdown into ``CodeRow`` dicts.

    ``existing`` is the uid-preserving path: for each parsed code, if a
    row in ``existing`` shares the same ``(family_name, name)``, its
    ``code_uid``/``family_uid`` are reused rather than minting new ones
    -- this is what lets a re-import of a lightly-edited codebook keep
    every code's identity (and therefore keep every ``coding_entries``
    row referencing it resolvable) instead of silently becoming N
    deletions + N additions. Family identity is likewise reused by
    ``family_name`` match against ``existing`` -- a genuine limitation
    (two same-named families in ``existing`` can't be told apart by name
    alone on a plain re-import; the normal structured-save path never
    hits this because it always carries uids explicitly).
    """
    structure = json.loads(parse_codebook_to_json(raw))

    existing_family_uid_by_name, existing_code_uid_by_key = _identity_indexes(existing)

    rows: list[CodeRow] = []
    position = 0
    for family in structure or []:
        family_name = str(family.get("family_name") or "").strip()
        family_uid = existing_family_uid_by_name.get(family_name) or uuid.uuid4().hex
        for code in family.get("codes") or []:
            name = str(code.get("code_name") or "").strip()
            if not name:
                continue
            content = str(code.get("content") or "")
            materialized = materialize_fields_from_body(content)
            rows.append(
                _new_code_row(
                    code_uid=existing_code_uid_by_key.get((family_name, name)) or uuid.uuid4().hex,
                    family_uid=family_uid,
                    family_name=family_name,
                    name=name,
                    body=materialized["body"] or "",
                    position=position,
                    definition=materialized["definition"],
                    inclusion=materialized["inclusion"],
                    exclusion=materialized["exclusion"],
                    keywords=materialized["keywords"],
                    example=materialized["example"],
                )
            )
            position += 1
    return rows


def render_codes_to_markdown(codes: Sequence[CodeRow]) -> str:
    """Render ``codes`` (already in ``position`` order) back to the
    ``### Code Family:``/``#### Code Name:`` markdown
    ``display_codebook.py`` and the apply/compare prompts expect.

    Groups by ``family_uid`` transitions in ``position`` order -- NOT by
    collecting all codes sharing a ``family_name`` together -- so two
    families that happen to share a name stay two separate blocks
    exactly where they occurred, rather than being silently merged into
    one on render. Always emits labeled lines from the structured
    columns (``definition``/``inclusion``/``exclusion``/``keywords``/
    ``example``). ``body`` is not a fallback display path.
    """
    ordered = sorted(codes, key=lambda c: c["position"])
    lines: list[str] = []
    current_family_uid: str | None = None
    for code in ordered:
        if code["family_uid"] != current_family_uid:
            if lines:
                lines.append("")
            lines.append(f"### Code Family: {code['family_name']}")
            current_family_uid = code["family_uid"]
        lines.append(f"#### Code Name: {code['name']}")
        body = _body_from_fields(
            definition=code.get("definition"),
            inclusion=code.get("inclusion"),
            exclusion=code.get("exclusion"),
            keywords=code.get("keywords"),
            example=code.get("example"),
        )
        if body:
            lines.extend(body.split("\n"))
    return "\n".join(lines).strip()
