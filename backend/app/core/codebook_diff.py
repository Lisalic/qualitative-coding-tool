"""Structural diff between two codebook versions -- a full outer join on
``code_uid``, not a name-similarity heuristic. This is the payoff of
giving every code a stable identity (see ``versioning_models.py``'s
``CodebookCode`` docstring): a rename is *recorded* by
``codebook_render.py``'s import path or the structured editor, so
detecting it here is exact set/field comparison, not inference.

Each change class is disjoint and computed from the same join:

- ``added``      -- uid only in the "to" version
- ``removed``    -- uid only in the "from" version
- ``renamed``    -- uid in both, ``name`` differs
- ``redefined``  -- uid in both, any of body/definition/inclusion/
                     exclusion/keywords/example differs
- ``moved``      -- uid in both, ``family_uid`` differs
- ``reordered``  -- uid in both, only ``position`` differs (reported
                     separately so a pure reorder never masquerades as a
                     substantive edit)
- ``unchanged``  -- uid in both, nothing differs

A code can be both renamed AND redefined AND moved at once; it appears
in every matching bucket. ``reordered``/``unchanged`` are mutually
exclusive with every other bucket and with each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


_CONTENT_FIELDS = ("body", "definition", "inclusion", "exclusion", "keywords", "example")


@dataclass
class CodebookDiff:
    added: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    renamed: list[dict] = field(default_factory=list)
    redefined: list[dict] = field(default_factory=list)
    moved: list[dict] = field(default_factory=list)
    reordered: list[dict] = field(default_factory=list)
    unchanged: list[dict] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.renamed or self.redefined or self.moved)


def _as_dict(code: Any) -> dict:
    if isinstance(code, Mapping):
        return dict(code)
    return {
        "code_uid": code.code_uid,
        "family_uid": code.family_uid,
        "family_name": code.family_name,
        "name": code.name,
        "body": code.body,
        "definition": code.definition,
        "inclusion": code.inclusion,
        "exclusion": code.exclusion,
        "keywords": code.keywords,
        "example": code.example,
        "position": code.position,
    }


def diff_codes(from_codes: Sequence[Any], to_codes: Sequence[Any]) -> CodebookDiff:
    """Diff two lists of codes (``CodebookCode`` ORM rows or plain dicts
    with the same fields), keyed on ``code_uid``.
    """
    by_uid_from = {c["code_uid"]: c for c in (_as_dict(c) for c in from_codes)}
    by_uid_to = {c["code_uid"]: c for c in (_as_dict(c) for c in to_codes)}

    result = CodebookDiff()

    for uid, code in by_uid_from.items():
        if uid not in by_uid_to:
            result.removed.append(code)

    for uid, to_code in by_uid_to.items():
        from_code = by_uid_from.get(uid)
        if from_code is None:
            result.added.append(to_code)
            continue

        renamed = from_code["name"] != to_code["name"]
        redefined = any(from_code.get(f) != to_code.get(f) for f in _CONTENT_FIELDS)
        moved = from_code["family_uid"] != to_code["family_uid"]

        entry = {
            "code_uid": uid,
            "from": from_code,
            "to": to_code,
        }
        if renamed:
            result.renamed.append(entry)
        if redefined:
            result.redefined.append(entry)
        if moved:
            result.moved.append(entry)

        if not (renamed or redefined or moved):
            if from_code["position"] != to_code["position"]:
                result.reordered.append(entry)
            else:
                result.unchanged.append(entry)

    return result
