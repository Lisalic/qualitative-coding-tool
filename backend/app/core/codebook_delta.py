"""Field-level delta between two codebook snapshots -- how a compacted
(non-materialized, non-keyframe) ``artifact_versions`` row stores what
changed instead of a full ``codebook_codes`` row set. See
``versioning_models.ArtifactVersion.codes_materialized``'s docstring and
``version_service._demote_if_eligible`` for where this fits into the
storage scheme.

Built on ``core/codebook_diff.py``'s uid-keyed join rather than a second,
parallel identity-matching differ -- ``diff_codes`` already gives an
exact ``added``/``removed`` set. ``modified``/``positions`` are computed
directly from the same two uid-indexed dicts, deliberately NOT from
``diff_codes``'s ``renamed``/``redefined``/``moved``/``reordered``
buckets: those are classified for *display* (a code that is both renamed
and reordered in one commit only ever lands in ``renamed``, never
``reordered`` -- see that module's docstring), which would silently drop
the position change from an encoded delta. Encoding needs the exhaustive
per-field truth, not the display classification.
"""

from __future__ import annotations

from typing import Any, Sequence

from backend.app.core.codebook_diff import _CONTENT_FIELDS, _as_dict, diff_codes

_MODIFIABLE_FIELDS = ("name", "family_uid", "family_name") + _CONTENT_FIELDS


def encode_delta(from_codes: Sequence[Any], to_codes: Sequence[Any]) -> dict:
    """``{"added": [<full CodeRow dict>, ...], "removed": [uid, ...],
    "modified": [{"code_uid": uid, "fields": {...changed fields...}}],
    "positions": {uid: new_position, ...}}`` -- ``from_codes``/
    ``to_codes`` are ``CodebookCode`` ORM rows or plain ``CodeRow``
    dicts, same as ``diff_codes``.
    """
    diff = diff_codes(from_codes, to_codes)

    from_by_uid = {c["code_uid"]: c for c in (_as_dict(c) for c in from_codes)}
    to_by_uid = {c["code_uid"]: c for c in (_as_dict(c) for c in to_codes)}

    modified = []
    positions = {}
    for uid, to_code in to_by_uid.items():
        from_code = from_by_uid.get(uid)
        if from_code is None:
            continue  # covered by `added` below
        changed_fields = {f: to_code[f] for f in _MODIFIABLE_FIELDS if from_code.get(f) != to_code.get(f)}
        if changed_fields:
            modified.append({"code_uid": uid, "fields": changed_fields})
        if from_code["position"] != to_code["position"]:
            positions[uid] = to_code["position"]

    return {
        "added": [dict(code) for code in diff.added],
        "removed": [code["code_uid"] for code in diff.removed],
        "modified": modified,
        "positions": positions,
    }


def apply_delta(codes: Sequence[Any], delta: dict | None) -> list[dict]:
    """Reconstruct the target snapshot: ``codes`` (the anchor's rows)
    patched by ``delta`` (from ``encode_delta``). Returns plain
    ``CodeRow``-shaped dicts, position-ordered. A falsy ``delta``
    (``None`` or ``{}``) returns ``codes`` unchanged, as dicts.
    """
    normalized = [_as_dict(c) for c in codes]
    by_uid: dict[str, dict] = {c["code_uid"]: c for c in normalized}
    if not delta:
        return sorted(by_uid.values(), key=lambda c: c["position"])

    for uid in delta.get("removed") or []:
        by_uid.pop(uid, None)
    for entry in delta.get("modified") or []:
        uid = entry["code_uid"]
        if uid in by_uid:
            by_uid[uid].update(entry["fields"])
    for uid, position in (delta.get("positions") or {}).items():
        if uid in by_uid:
            by_uid[uid]["position"] = position
    for code in delta.get("added") or []:
        by_uid[code["code_uid"]] = dict(code)

    return sorted(by_uid.values(), key=lambda c: c["position"])
