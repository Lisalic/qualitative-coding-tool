"""Shared vocabulary for the two kinds of coded content, ``submission``
(post) and ``comment``.

Reddit's own fullname convention is reused as the wire encoding: a
qualified id is ``t3_<id>`` for a submission or ``t1_<id>`` for a comment
-- the prefixes ``import_db.py`` already strips off ``Submission.id`` and
``Comment.link_id``/``parent_id`` at import time, so a bare (unprefixed)
id is exactly what every artifact produced before this module existed
already contains. That is why :func:`split_item_id` treats an unprefixed
id as ``"submission"`` -- it is not a guess, it is the historical default
every pre-existing ``coding_entries`` row and every already-saved coding
artifact was written under.

The type is encoded in the id string itself (not a separate ``TYPE:``
line in the coding DSL) because View Coding round-trips a coding
artifact's text through ``frontend/src/lib/codingUtils.js``'s
``parseCodingData``/``formatCodingData`` on every edit-and-save. A
sibling line would be silently dropped the first time a user edits and
saves; a prefix embedded in the id they already treat as an opaque
string survives for free. ``frontend/src/lib/itemIds.js`` mirrors this
module exactly -- keep the two in sync.
"""

from __future__ import annotations

SUBMISSION = "submission"
COMMENT = "comment"

_PREFIXES = {
    SUBMISSION: "t3_",
    COMMENT: "t1_",
}


def qualify_item_id(row_type: str, raw_id: str) -> str:
    """Prefix ``raw_id`` with its type marker, e.g. ``("comment", "abc")
    -> "t1_abc"``. ``row_type`` must be :data:`SUBMISSION` or
    :data:`COMMENT`.
    """
    prefix = _PREFIXES.get(row_type)
    if prefix is None:
        raise ValueError(f"Unknown row_type: {row_type!r}")
    return f"{prefix}{raw_id}"


def split_item_id(qualified_id: str) -> tuple[str, str]:
    """Split a possibly-prefixed id back into ``(row_type, raw_id)``.

    An id with no recognized prefix is treated as :data:`SUBMISSION` --
    see the module docstring for why that is the correct default rather
    than an error.
    """
    value = qualified_id or ""
    for row_type, prefix in _PREFIXES.items():
        if value.startswith(prefix):
            return row_type, value[len(prefix):]
    return SUBMISSION, value
