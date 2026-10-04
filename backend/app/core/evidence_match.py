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

# Invisible characters that copy-pasted text carries but a model's echo
# of it never does. Dropped from both sides.
_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\u2060\ufeff")


def normalize_with_index_map(text: str) -> tuple[str, list[int]]:
    """``(normalized_text, index_map)`` where ``index_map[i]`` is the
    offset in ``text`` that ``normalized_text[i]`` came from.

    Normalization: NFKC, the substitutions in :data:`_CHAR_FOLD`,
    casefolding, dropping :data:`_ZERO_WIDTH` characters, and collapsing
    every run of whitespace to a single space. Leading whitespace is
    dropped entirely. NFKC runs on a base character together with the
    combining marks after it, so decomposed text (``e`` + U+0301, common
    from macOS/iOS) matches its precomposed form (``é``).

    The index map is what makes a normalized match reversible -- without
    it a hit in normalized space could not be translated into a highlight
    range in the text the user actually sees.
    """
    normalized_chars: list[str] = []
    index_map: list[int] = []
    previous_was_space = True  # True so leading whitespace is skipped

    text = text or ""
    original_index = 0
    while original_index < len(text):
        raw_char = text[original_index]
        char = _CHAR_FOLD.get(raw_char, raw_char)

        if raw_char in _ZERO_WIDTH:
            original_index += 1
            continue

        if char.isspace():
            original_index += 1
            if previous_was_space:
                continue
            normalized_chars.append(" ")
            index_map.append(original_index - 1)
            previous_was_space = True
            continue

        cluster_end = _cluster_end(text, original_index)
        cluster = char + text[original_index + 1:cluster_end]
        # NFKC can expand one cluster into several characters (e.g. a
        # ligature); every one maps back to the cluster's first index.
        for decomposed in unicodedata.normalize("NFKC", cluster).casefold():
            normalized_chars.append(decomposed)
            index_map.append(original_index)
        previous_was_space = False
        original_index = cluster_end

    return "".join(normalized_chars), index_map


def normalize_label(text: str | None) -> str:
    """A short label (a code or family name) folded for comparison --
    the same normalization quotes get, so "Children’s  needs" and
    "children's needs" are one name.
    """
    return normalize_with_index_map(text or "")[0].strip()


def _cluster_end(text: str, index: int) -> int:
    """One past the last combining mark following ``text[index]``."""
    end = index + 1
    while end < len(text) and unicodedata.combining(text[end]):
        end += 1
    return end


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
    normalized_quote = normalize_with_index_map(quote)[0].rstrip()
    if not normalized_quote:
        return None

    hit = normalized_content.find(normalized_quote)
    if hit == -1:
        return None

    start = index_map[hit]
    # ``index_map`` records where each normalized character *started*, so
    # the end of the span is one past the original character that produced
    # the quote's final normalized character.
    end = _cluster_end(content, index_map[hit + len(normalized_quote) - 1])
    return start, end
