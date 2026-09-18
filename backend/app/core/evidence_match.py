"""Resolve an AI-supplied evidence quote to exact character offsets in the
post/comment text it claims to come from -- the anti-hallucination check
that gates every ``coding_entries`` write.

The problem this solves: models reliably identify the *right* span but do
not reproduce it byte-for-byte. They collapse newlines to spaces, turn
``"`` into ``"``, ``--`` into ``—``, and vary case. A strict
``content.find(quote)`` therefore rejects a large share of perfectly
correct codings, while a fuzzy match that only answers "yes/no" can't
tell the UI *where* to paint the highlight.

So matching is done on a normalized copy of the text while keeping an
index map back to the original, and the hit is reported as offsets into
the **original** string. That buys both properties at once:

* text that genuinely isn't in the post still fails (no hallucinated
  evidence reaches the database), and
* a hit always resolves to exact original offsets, so highlighting is
  precise by construction -- the frontend never re-searches for the quote
  at render time.

Offsets are always relative to the item's own body text
(``Submission.selftext`` / ``Comment.body``), which is exactly the string
View Coding's reader pane renders, so stored offsets and painted
highlights share one coordinate system.
"""

from __future__ import annotations

import unicodedata

# Characters models routinely substitute when echoing a quote back.
# Folded to their ASCII equivalents on both sides of the comparison.
_CHAR_FOLD = {
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "„": '"',
    "‘": "'",  # left single quote
    "’": "'",  # right single quote / apostrophe
    "‚": "'",
    "–": "-",  # en dash
    "—": "-",  # em dash
    "−": "-",  # minus sign
    " ": " ",  # non-breaking space
}


def normalize_with_index_map(text: str) -> tuple[str, list[int]]:
    """``(normalized_text, index_map)`` where ``index_map[i]`` is the
    offset in ``text`` that ``normalized_text[i]`` came from.

    Normalization: NFKC, the substitutions in :data:`_CHAR_FOLD`,
    casefolding, and collapsing every run of whitespace to a single
    space. Leading whitespace is dropped entirely.

    The index map is what makes a normalized match reversible -- without
    it a hit in normalized space could not be translated into a highlight
    range in the text the user actually sees.
    """
    normalized_chars: list[str] = []
    index_map: list[int] = []
    previous_was_space = True  # True so leading whitespace is skipped

    for original_index, raw_char in enumerate(text or ""):
        char = _CHAR_FOLD.get(raw_char, raw_char)

        if char.isspace():
            if previous_was_space:
                continue
            normalized_chars.append(" ")
            index_map.append(original_index)
            previous_was_space = True
            continue

        # NFKC can expand one character into several (e.g. a ligature);
        # every resulting character maps back to the same original index.
        for decomposed in unicodedata.normalize("NFKC", char).casefold():
            normalized_chars.append(decomposed)
            index_map.append(original_index)
        previous_was_space = False

    return "".join(normalized_chars), index_map


def find_quote(content: str, quote: str) -> tuple[int, int] | None:
    """Locate ``quote`` inside ``content``, returning ``(start, end)``
    offsets into the **original** ``content`` (suitable for
    ``content[start:end]``), or ``None`` when the quote genuinely does not
    occur.

    Tries an exact match first -- the common case when the model copies
    faithfully, and the cheapest -- then falls back to the normalized
    search described in this module's docstring.
    """
    if not content or not quote:
        return None

    exact_index = content.find(quote)
    if exact_index != -1:
        return exact_index, exact_index + len(quote)

    normalized_content, index_map = normalize_with_index_map(content)
    normalized_quote, _ = normalize_with_index_map(quote)
    if not normalized_quote:
        return None

    hit = normalized_content.find(normalized_quote)
    if hit == -1:
        return None

    start = index_map[hit]
    # ``index_map`` records where each normalized character *started*, so
    # the end of the span is one past the original character that produced
    # the quote's final normalized character.
    end = index_map[hit + len(normalized_quote) - 1] + 1
    return start, end
