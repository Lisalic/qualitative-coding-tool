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
- ``matched_by_name`` -- for unrelated codebooks with disjoint uids,
                         documented matching by normalized name.

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
    matched_by_name: list[dict] = field(default_factory=list)
    unrelated_histories: bool = False

    def is_empty(self) -> bool:
        return not (
            self.added
            or self.removed
            or self.renamed
            or self.redefined
            or self.moved
            or self.matched_by_name
        )


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


def diff_codes(
    from_codes: Sequence[Any],
    to_codes: Sequence[Any],
    *,
    match_unrelated: bool = True,
) -> CodebookDiff:
    """Diff two lists of codes (``CodebookCode`` ORM rows or plain dicts
    with the same fields), keyed on ``code_uid``.

    If ``match_unrelated`` is True and the codebooks have completely disjoint
    identities (unrelated histories), codes with matching names are paired
    under ``matched_by_name`` per documented cross-artifact comparison rules.
    """
    by_uid_from = {c["code_uid"]: c for c in (_as_dict(c) for c in from_codes)}
    by_uid_to = {c["code_uid"]: c for c in (_as_dict(c) for c in to_codes)}

    result = CodebookDiff()

    # Detect unrelated histories
    shared_uids = set(by_uid_from) & set(by_uid_to)
    if by_uid_from and by_uid_to and not shared_uids:
        result.unrelated_histories = True

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

    # Documented rule: if unrelated histories and match_unrelated is enabled,
    # match codes in removed and added by normalized name
    if result.unrelated_histories and match_unrelated:
        from_by_name = {c["name"].strip().lower(): c for c in result.removed}
        to_by_name = {c["name"].strip().lower(): c for c in result.added}
        common_names = set(from_by_name) & set(to_by_name)

        if common_names:
            new_removed = []
            for c in result.removed:
                norm = c["name"].strip().lower()
                if norm in common_names:
                    match_from = c
                    match_to = to_by_name[norm]
                    result.matched_by_name.append(
                        {
                            "name": match_from["name"],
                            "code_uid_from": match_from["code_uid"],
                            "code_uid_to": match_to["code_uid"],
                            "from": match_from,
                            "to": match_to,
                            "redefined": any(
                                match_from.get(f) != match_to.get(f) for f in _CONTENT_FIELDS
                            ),
                            "moved": match_from["family_uid"] != match_to["family_uid"],
                        }
                    )
                else:
                    new_removed.append(c)
            result.removed = new_removed

            # Filter out matched codes from added
            result.added = [
                c for c in result.added if c["name"].strip().lower() not in common_names
            ]

    return result
