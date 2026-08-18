"""Tests for backend/scripts/tag_expansion.py -- the pure helpers.

`expand_tags_via_openrouter` (network) is covered separately in the AI
route tests via a patched `get_client`/OpenAI seam, not here.
"""

import time

import pytest

from backend.scripts.tag_expansion import (
    TagExpansionError,
    _extract_error_code,
    _normalize_term,
    _parse_expansion_json,
    _strip_json_fences,
    comment_body_tag_predicate_sql,
    normalize_and_cap_terms,
    parse_filter_tags_input,
    submission_text_tag_predicate_sql,
)


# ---------------------------------------------------------------------------
# TagExpansionError
# ---------------------------------------------------------------------------


class TestTagExpansionError:
    def test_message_and_default_code(self) -> None:
        err = TagExpansionError("boom")
        assert str(err) == "boom"
        assert err.code == 0

    def test_custom_code_preserved(self) -> None:
        err = TagExpansionError("boom", code=502)
        assert err.code == 502

    def test_is_a_plain_exception(self) -> None:
        with pytest.raises(Exception):
            raise TagExpansionError("x")


# ---------------------------------------------------------------------------
# _extract_error_code
# ---------------------------------------------------------------------------


class TestExtractErrorCode:
    def test_extracts_from_message(self) -> None:
        assert _extract_error_code(Exception("Error code: 404")) == 404

    def test_extracts_without_space(self) -> None:
        assert _extract_error_code(Exception("Error code:404")) == 404

    def test_unanchored_search_finds_code_mid_string(self) -> None:
        assert _extract_error_code(Exception("x Error code: 502 y")) == 502

    def test_boundary_bug_four_digit_code_greedily_takes_first_three(self) -> None:
        # \d{3} has no trailing boundary, so "4041" yields 404, not a miss.
        assert _extract_error_code(Exception("Error code: 4041")) == 404

    def test_lowercase_does_not_match(self) -> None:
        err = Exception("error code: 404")
        assert _extract_error_code(err) == 0

    def test_falls_back_to_status_code_attribute(self) -> None:
        class Err(Exception):
            status_code = 429

        assert _extract_error_code(Err("no code here")) == 429

    def test_status_code_none_falls_back_to_zero(self) -> None:
        class Err(Exception):
            status_code = None

        assert _extract_error_code(Err("x")) == 0

    def test_message_regex_wins_over_status_code_attribute(self) -> None:
        class Err(Exception):
            status_code = 500

        assert _extract_error_code(Err("Error code: 429")) == 429

    def test_plain_exception_with_no_signal_returns_zero(self) -> None:
        assert _extract_error_code(Exception("boom")) == 0


# ---------------------------------------------------------------------------
# parse_filter_tags_input
# ---------------------------------------------------------------------------


class TestParseFilterTagsInput:
    @pytest.mark.parametrize("raw", [None, "", "   ", "\n"])
    def test_blank_input_returns_empty_list(self, raw) -> None:
        assert parse_filter_tags_input(raw) == []

    def test_splits_on_commas(self) -> None:
        assert parse_filter_tags_input("a,b,c") == ["a", "b", "c"]

    def test_splits_on_newlines(self) -> None:
        assert parse_filter_tags_input("a\nb\nc") == ["a", "b", "c"]

    def test_consecutive_delimiters_collapse(self) -> None:
        assert parse_filter_tags_input("a,,b") == ["a", "b"]
        assert parse_filter_tags_input("a,\n,b") == ["a", "b"]

    def test_does_not_split_on_semicolon_or_tab(self) -> None:
        assert parse_filter_tags_input("a;b") == ["a;b"]
        assert parse_filter_tags_input("a\tb") == ["a\tb"]

    def test_leading_and_trailing_delimiters_stripped(self) -> None:
        assert parse_filter_tags_input(",a,") == ["a"]

    def test_no_dedupe_no_case_folding(self) -> None:
        assert parse_filter_tags_input("a,A,a") == ["a", "A", "a"]

    def test_non_str_input_is_stringified(self) -> None:
        assert parse_filter_tags_input(123) == ["123"]  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _normalize_term
# ---------------------------------------------------------------------------


class TestNormalizeTerm:
    def test_collapses_internal_whitespace(self) -> None:
        assert _normalize_term(" a   b \n c ") == "a b c"

    def test_empty_and_whitespace_only(self) -> None:
        assert _normalize_term("") == ""
        assert _normalize_term("   \t\n  ") == ""

    def test_exactly_80_chars_unchanged(self) -> None:
        s = "x" * 80
        assert _normalize_term(s) == s

    def test_81_chars_truncated_to_80(self) -> None:
        s = "x" * 81
        out = _normalize_term(s)
        assert len(out) == 80
        assert out == "x" * 80


# ---------------------------------------------------------------------------
# normalize_and_cap_terms
# ---------------------------------------------------------------------------


class TestNormalizeAndCapTerms:
    def test_basic(self) -> None:
        assert normalize_and_cap_terms(["alpha", "beta"]) == ["alpha", "beta"]

    def test_drops_sub_two_char_terms(self) -> None:
        assert normalize_and_cap_terms(["a", "ai", "ok", "x"]) == ["ai", "ok"]

    def test_dedupe_is_case_insensitive_keeps_first_casing(self) -> None:
        assert normalize_and_cap_terms(["Anxiety", "anxiety", "ANXIETY"]) == ["Anxiety"]

    def test_whitespace_normalization_feeds_dedupe(self) -> None:
        # "panic  attack" (double space) normalizes to "panic attack"
        # before the dedupe key is computed, so the two collapse to one.
        assert normalize_and_cap_terms(["panic  attack", "panic attack"]) == ["panic attack"]

    def test_non_str_entries_are_skipped_without_error(self) -> None:
        result = normalize_and_cap_terms([None, "", 0, [], 5, True, "ok"])  # type: ignore[list-item]
        assert result == ["ok"]

    def test_empty_list(self) -> None:
        assert normalize_and_cap_terms([]) == []

    def test_none_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            normalize_and_cap_terms(None)  # type: ignore[arg-type]

    def test_order_preserved_not_sorted(self) -> None:
        assert normalize_and_cap_terms(["zebra", "apple"]) == ["zebra", "apple"]

    def test_truncation_before_dedupe_collapses_distinct_long_strings(self) -> None:
        a = "x" * 80 + "AAAA"
        b = "x" * 80 + "BBBB"
        # Both truncate to the same 80-char prefix before the dedupe key
        # is computed, so only one survives.
        assert normalize_and_cap_terms([a, b]) == ["x" * 80]

    # -- confirmed bug: cap check happened after append -----------------

    def test_cap_zero_returns_empty_list(self) -> None:
        """Confirmed bug: `if len(out) >= cap: break` ran AFTER the
        append, so cap=0 returned one element instead of zero. Fixed by
        checking the cap before appending.
        """
        assert normalize_and_cap_terms(["alpha", "beta", "gamma"], cap=0) == []

    def test_negative_cap_returns_empty_list(self) -> None:
        assert normalize_and_cap_terms(["alpha", "beta"], cap=-5) == []

    @pytest.mark.parametrize("cap", [1, 2, 3])
    def test_cap_n_returns_exactly_n_when_enough_terms(self, cap: int) -> None:
        terms = ["alpha", "beta", "gamma", "delta"]
        assert len(normalize_and_cap_terms(terms, cap=cap)) == cap

    def test_cap_larger_than_input_returns_all(self) -> None:
        assert normalize_and_cap_terms(["alpha", "beta"], cap=50) == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# _strip_json_fences / _parse_expansion_json
# ---------------------------------------------------------------------------


class TestStripJsonFences:
    def test_strips_json_fence(self) -> None:
        assert _strip_json_fences("```json\n{}\n```") == "{}"

    def test_strips_plain_fence(self) -> None:
        assert _strip_json_fences("```\n{}\n```") == "{}"

    def test_unterminated_fence(self) -> None:
        assert _strip_json_fences("```json\n{}") == "{}"

    def test_only_activates_when_content_starts_with_fence(self) -> None:
        raw = "text\n```json\n{}\n```"
        assert _strip_json_fences(raw) == raw  # unchanged: fences intact

    def test_fence_alone_becomes_empty(self) -> None:
        assert _strip_json_fences("```") == ""

    def test_empty_string(self) -> None:
        assert _strip_json_fences("") == ""

    def test_content_line_with_embedded_backticks_is_preserved(self) -> None:
        # The fence-line filter only drops lines whose STRIPPED form
        # *starts with* ```, so a mid-line ``` embedded in real content
        # (not on its own line) survives untouched.
        raw = '```\n{"a": "```"}\n```'
        assert _strip_json_fences(raw) == '{"a": "```"}'

    def test_content_line_that_itself_starts_with_backticks_is_dropped(self) -> None:
        # But a line that genuinely *starts* with ``` is removed even if
        # it's meant as JSON content, not a fence delimiter -- corrupting
        # otherwise-valid JSON.
        raw = '```\n{"a": 1,\n```"b": 2}\n```'
        assert _strip_json_fences(raw) == '{"a": 1,'

    def test_indented_fence_lines_are_matched_but_not_reindented(self) -> None:
        raw = "   ```\ncontent\n   ```"
        assert _strip_json_fences(raw) == "content"


class TestParseExpansionJson:
    def test_valid_object(self) -> None:
        assert _parse_expansion_json('{"a": 1}') == {"a": 1}

    def test_fenced_valid_json(self) -> None:
        assert _parse_expansion_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_empty_object_accepted(self) -> None:
        assert _parse_expansion_json("{}") == {}

    def test_invalid_json_raises_502(self) -> None:
        with pytest.raises(TagExpansionError) as exc_info:
            _parse_expansion_json("{not json")
        assert exc_info.value.code == 502
        assert "invalid JSON" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    @pytest.mark.parametrize("raw", ["[]", "[1,2]", "null", "123", '"str"'])
    def test_non_object_json_raises_502(self, raw: str) -> None:
        with pytest.raises(TagExpansionError) as exc_info:
            _parse_expansion_json(raw)
        assert exc_info.value.code == 502
        assert "must be an object" in str(exc_info.value)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(TagExpansionError):
            _parse_expansion_json("")


# ---------------------------------------------------------------------------
# SQL predicate builders
# ---------------------------------------------------------------------------


class TestSubmissionTextTagPredicateSql:
    def test_empty_terms_returns_empty(self) -> None:
        assert submission_text_tag_predicate_sql([]) == ("", {})

    def test_single_term(self) -> None:
        sql, bind = submission_text_tag_predicate_sql(["Anxiety"])
        assert sql == (
            " AND (position(lower(:tag_sub_0) in "
            "lower(coalesce(title, '') || ' ' || coalesce(selftext, ''))) > 0)"
        )
        assert bind == {"tag_sub_0": "anxiety"}  # lowercased

    def test_multiple_terms_use_distinct_keys(self) -> None:
        sql, bind = submission_text_tag_predicate_sql(["a", "b"])
        assert "tag_sub_0" in bind and "tag_sub_1" in bind
        assert " OR " in sql

    def test_user_text_lands_only_in_bind_params(self) -> None:
        malicious = "'; DROP TABLE x--"
        sql, bind = submission_text_tag_predicate_sql([malicious])
        assert malicious not in sql
        assert malicious.lower() in bind.values()

    def test_none_term_raises(self) -> None:
        with pytest.raises(AttributeError):
            submission_text_tag_predicate_sql([None])  # type: ignore[list-item]


class TestCommentBodyTagPredicateSql:
    def test_empty_terms_returns_empty(self) -> None:
        assert comment_body_tag_predicate_sql([]) == ("", {})

    def test_uses_distinct_key_prefix_from_submission_variant(self) -> None:
        _, sub_bind = submission_text_tag_predicate_sql(["x"])
        _, com_bind = comment_body_tag_predicate_sql(["x"])
        # Different prefixes mean the two dicts can be merged into one
        # query's bind params without key collision.
        assert set(sub_bind.keys()).isdisjoint(com_bind.keys())
        assert "tag_com_0" in com_bind
