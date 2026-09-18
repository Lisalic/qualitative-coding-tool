"""Tests for backend/app/core/evidence_match.py -- the anti-hallucination
quote resolver that gates every ``coding_entries`` write (see
``backend/app/services/coding_service.py::_validate_and_resolve_coding_entries``).
"""

from backend.app.core.evidence_match import find_quote, normalize_with_index_map


class TestNormalizeWithIndexMap:
    def test_empty_string(self) -> None:
        normalized, index_map = normalize_with_index_map("")
        assert normalized == ""
        assert index_map == []

    def test_none_treated_as_empty(self) -> None:
        normalized, index_map = normalize_with_index_map(None)
        assert normalized == ""
        assert index_map == []

    def test_casefolds(self) -> None:
        normalized, _ = normalize_with_index_map("Hello WORLD")
        assert normalized == "hello world"

    def test_collapses_internal_whitespace_runs(self) -> None:
        normalized, _ = normalize_with_index_map("a   b\n\nc")
        assert normalized == "a b c"

    def test_strips_leading_whitespace(self) -> None:
        normalized, _ = normalize_with_index_map("   hello")
        assert normalized == "hello"

    def test_folds_curly_quotes_and_dashes_to_ascii(self) -> None:
        normalized, _ = normalize_with_index_map("“hello—world”")
        assert normalized == '"hello-world"'

    def test_folds_nbsp_to_space(self) -> None:
        normalized, _ = normalize_with_index_map("a b")
        assert normalized == "a b"

    def test_index_map_length_matches_normalized_length(self) -> None:
        text = "Hello   World\n\nagain"
        normalized, index_map = normalize_with_index_map(text)
        assert len(index_map) == len(normalized)

    def test_index_map_resolves_back_to_original_characters(self) -> None:
        text = "  Hello   World  "
        normalized, index_map = normalize_with_index_map(text)
        # Every normalized char's mapped original index, case-folded,
        # should reproduce the normalized character (whitespace excepted,
        # since runs collapse to a single synthetic space).
        for i, ch in enumerate(normalized):
            if ch == " ":
                continue
            assert text[index_map[i]].casefold() == ch


class TestFindQuote:
    def test_empty_content_or_quote_returns_none(self) -> None:
        assert find_quote("", "x") is None
        assert find_quote("x", "") is None
        assert find_quote(None, "x") is None
        assert find_quote("x", None) is None

    def test_exact_match_returns_original_offsets(self) -> None:
        content = "The cat sat on the mat."
        result = find_quote(content, "cat sat")
        assert result == (4, 11)
        assert content[result[0] : result[1]] == "cat sat"

    def test_exact_match_prefers_first_occurrence(self) -> None:
        content = "cat cat cat"
        result = find_quote(content, "cat")
        assert result == (0, 3)

    def test_genuine_hallucination_returns_none(self) -> None:
        content = "The cat sat on the mat."
        assert find_quote(content, "the dog ran away") is None

    def test_case_insensitive_match_resolves_to_exact_original_offsets(self) -> None:
        content = "She was Very Anxious about it."
        result = find_quote(content, "very anxious")
        assert result is not None
        start, end = result
        assert content[start:end] == "Very Anxious"

    def test_whitespace_collapsed_in_source_still_matches(self) -> None:
        # The model turns a newline into a space when echoing a quote --
        # the quote should still resolve, and to the *original* (un-
        # collapsed) span.
        content = "income was low\n\nvery low indeed"
        result = find_quote(content, "income was low very low")
        assert result is not None
        start, end = result
        assert content[start:end] == "income was low\n\nvery low"

    def test_curly_quotes_in_source_matched_by_straight_quote_query(self) -> None:
        content = 'She said “hello there” and left.'
        result = find_quote(content, '"hello there"')
        assert result is not None
        start, end = result
        assert content[start:end] == "“hello there”"

    def test_em_dash_in_source_matched_by_ascii_hyphen_query(self) -> None:
        # One em dash character folds to one ASCII hyphen -- a run of
        # several ASCII hyphens (e.g. a model writing "--" for an em dash)
        # is a different, unhandled case, not what this folds.
        content = "income was low—very low indeed"
        result = find_quote(content, "income was low-very low")
        assert result is not None
        start, end = result
        assert content[start:end] == "income was low—very low"

    def test_normalized_quote_that_is_empty_after_normalization_returns_none(self) -> None:
        # A quote that's pure whitespace normalizes to "" -- must not
        # match a genuinely empty normalized_quote against everything.
        assert find_quote("some real content", "   ") is None

    def test_quote_longer_than_content_returns_none(self) -> None:
        assert find_quote("short", "this quote is much longer than the content") is None

    def test_match_at_the_very_end_of_content(self) -> None:
        content = "some text ending here"
        result = find_quote(content, "ending here")
        assert result == (10, 21)

    def test_match_at_the_very_start_of_content(self) -> None:
        content = "Starting text goes on"
        result = find_quote(content, "Starting text")
        assert result == (0, 13)
