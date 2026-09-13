"""Roll up a coded row's per-quote ``coder`` values into one label.

A row's live ``coding_entries`` rows each carry their own
``coder`` (``storage_models.CODER_HUMAN``/``CODER_AI``) -- see that
module's docstring for why attribution lives per-quote rather than per
row. "AI" / "Human" / "Both" is a *view* over that set, computed here
rather than stored, so a hand-added quote next to an accepted AI one
just works without a write path that has to keep a redundant row-level
column in sync.

Kept as one pure function in ``core/`` (no DB session, no ORM import),
matching ``codebook_diff.py``/``evidence_match.py``'s convention of
putting the actual decision logic somewhere unit-testable without a
database.
"""

from __future__ import annotations

from typing import Iterable, Optional

from backend.app.storage_models import CODER_AI, CODER_HUMAN

# Roll-up result values.
ROLLUP_AI = "ai"
ROLLUP_HUMAN = "human"
ROLLUP_BOTH = "both"


def roll_up(coders: Iterable[str]) -> Optional[str]:
    """Reduce a row's live entries' ``coder`` values to one label.

    Returns ``None`` for an uncoded row (no entries at all) -- distinct
    from any real coder value, so a caller can't mistake "nobody coded
    this" for "a human coded this". Returns :data:`ROLLUP_BOTH` as soon
    as both a human- and an AI-attributed entry appear on the same row,
    regardless of how many of each.
    """
    seen_human = False
    seen_ai = False
    for coder in coders:
        if coder == CODER_AI:
            seen_ai = True
        elif coder == CODER_HUMAN:
            seen_human = True
        if seen_human and seen_ai:
            return ROLLUP_BOTH
    if seen_ai:
        return ROLLUP_AI
    if seen_human:
        return ROLLUP_HUMAN
    return None
