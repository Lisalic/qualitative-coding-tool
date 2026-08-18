"""Tests for backend/scripts/display_codebook.py::parse_codebook_to_json.

The function returns a JSON *string* (json.dumps(..., indent=2)), so every
assertion here parses it back with json.loads before inspecting structure.
"""

import json

import pytest

from backend.scripts.display_codebook import parse_codebook_to_json


def parsed(raw_text: str):
    return json.loads(parse_codebook_to_json(raw_text))


class TestBasicStructure:
    def test_single_family_single_code(self) -> None:
        raw = (
            "### Code Family: Anxiety\n"
            "Family description.\n"
            "#### Code Name: Panic\n"
            "Code description."
        )
        result = parsed(raw)
        assert result == [
            {
                "family_name": "Anxiety",
                "content": "Family description.",
                "codes": [{"code_name": "Panic", "content": "Code description."}],
            }
        ]

    def test_empty_input_returns_empty_list(self) -> None:
        assert parsed("") == []

    @pytest.mark.parametrize("raw", ["   ", "\n\n\n"])
    def test_whitespace_only_input_returns_empty_list(self, raw: str) -> None:
        assert parsed(raw) == []

    def test_none_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            parse_codebook_to_json(None)  # type: ignore[arg-type]

    def test_multiple_families_and_codes(self) -> None:
        raw = (
            "### Code Family: A\n"
            "#### Code Name: A1\n"
            "a1 content\n"
            "#### Code Name: A2\n"
            "a2 content\n"
            "### Code Family: B\n"
            "#### Code Name: B1\n"
            "b1 content\n"
        )
        result = parsed(raw)
        assert [f["family_name"] for f in result] == ["A", "B"]
        assert [c["code_name"] for c in result[0]["codes"]] == ["A1", "A2"]
        assert result[0]["codes"][0]["content"] == "a1 content"
        assert result[0]["codes"][1]["content"] == "a2 content"
        assert result[1]["codes"][0]["content"] == "b1 content"


class TestOrphanContentDropped:
    def test_prose_before_any_family_is_dropped(self) -> None:
        assert parsed("just some prose\nmore prose") == []

    def test_code_before_any_family_is_dropped_from_output(self) -> None:
        # current_code is created but never appended anywhere without a
        # current_family, so it silently vanishes.
        assert parsed("#### Code Name: X\nbody") == []


class TestContentAttachment:
    def test_family_content_only_survives_before_first_code(self) -> None:
        raw = (
            "### Code Family: F\n"
            "prose A\n"
            "#### Code Name: C1\n"
            "prose B\n"
            "prose C\n"
        )
        result = parsed(raw)
        assert result[0]["content"] == "prose A"
        assert result[0]["codes"][0]["content"] == "prose B\nprose C"

    def test_blank_lines_between_paragraphs_collapse(self) -> None:
        raw = "### Code Family: F\np1\n\np2\n"
        result = parsed(raw)
        assert result[0]["content"] == "p1\np2"

    def test_empty_family_has_empty_content_and_no_codes(self) -> None:
        result = parsed("### Code Family: X")
        assert result == [{"family_name": "X", "content": "", "codes": []}]

    def test_empty_code_has_empty_content(self) -> None:
        result = parsed("### Code Family: X\n#### Code Name: Y")
        assert result[0]["codes"] == [{"code_name": "Y", "content": ""}]

    def test_consecutive_families_both_empty(self) -> None:
        raw = "### Code Family: A\n### Code Family: B\n"
        result = parsed(raw)
        assert len(result) == 2
        assert result[0]["content"] == "" and result[0]["codes"] == []
        assert result[1]["content"] == "" and result[1]["codes"] == []

    def test_duplicate_family_names_are_not_merged(self) -> None:
        raw = "### Code Family: Dup\na\n### Code Family: Dup\nb\n"
        result = parsed(raw)
        assert len(result) == 2
        assert result[0]["family_name"] == result[1]["family_name"] == "Dup"
        assert result[0]["content"] == "a"
        assert result[1]["content"] == "b"


class TestMarkerParsing:
    def test_blank_family_name(self) -> None:
        result = parsed("### Code Family:   \n")
        assert result[0]["family_name"] == ""

    def test_blank_code_name(self) -> None:
        result = parsed("### Code Family: F\n#### Code Name:   \n")
        assert result[0]["codes"][0]["code_name"] == ""

    def test_only_text_after_first_marker_match_is_captured(self) -> None:
        # The regex match is anchored at line start and captures everything
        # after the first "Code Family:" -- unlike the old str.replace
        # approach, a second occurrence later in the line is not stripped out.
        result = parsed("### Code Family: A ### Code Family: B\n")
        assert result[0]["family_name"] == "A ### Code Family: B"

    @pytest.mark.parametrize(
        "line,expected_name",
        [
            ("###Code Family: X", "X"),  # no space after ###
            ("### Code family: X", "X"),  # lowercase 'family'
            ("## Code Family: X", "X"),  # only 2 hashes
            ("Code Family: X", "X"),  # no markdown prefix at all
        ],
    )
    def test_near_miss_family_markers_still_open_a_family(self, line: str, expected_name: str) -> None:
        # The parser is deliberately lenient about hash count, spacing, and
        # case, since the model's actual output doesn't reliably match the
        # exact "### Code Family:" prefix the prompt asks for -- see
        # known-issues.md #2.
        result = parsed(line)
        assert result[0]["family_name"] == expected_name

    def test_missing_colon_falls_through_to_content(self) -> None:
        # No colon at all means the label can't be distinguished from
        # ordinary prose, so this still doesn't open a family.
        assert parsed("### Code Family X") == []

    def test_indented_markers_still_match(self) -> None:
        result = parsed("    ### Code Family: X\n")
        assert result[0]["family_name"] == "X"

    def test_family_marker_wins_over_embedded_code_marker_text(self) -> None:
        result = parsed("### Code Family: #### Code Name: X\n")
        assert result[0]["family_name"] == "#### Code Name: X"

    def test_unicode_family_name_round_trips_through_json(self) -> None:
        result = parsed("### Code Family: Ångst\n")
        assert result[0]["family_name"] == "Ångst"


class TestUnprefixedModelOutput:
    """Regression coverage for known-issues.md #2: the generator's system
    prompt didn't always come back with markdown-prefixed headers, so the
    parser needs to handle unprefixed and mixed-format output too."""

    def test_fully_unprefixed_output_parses(self) -> None:
        raw = (
            "Code Family: Anxiety\n"
            "Family description.\n"
            "Code Name: Panic\n"
            "Code description."
        )
        result = parsed(raw)
        assert result == [
            {
                "family_name": "Anxiety",
                "content": "Family description.",
                "codes": [{"code_name": "Panic", "content": "Code description."}],
            }
        ]

    def test_mixed_prefixed_and_unprefixed_families_both_parse(self) -> None:
        raw = (
            "### Code Family: A\n"
            "#### Code Name: A1\n"
            "a1 content\n"
            "Code Family: B\n"
            "Code Name: B1\n"
            "b1 content\n"
        )
        result = parsed(raw)
        assert [f["family_name"] for f in result] == ["A", "B"]
        assert [c["code_name"] for c in result[0]["codes"]] == ["A1"]
        assert [c["code_name"] for c in result[1]["codes"]] == ["B1"]


class TestReturnType:
    def test_returns_a_json_string_not_a_list(self) -> None:
        out = parse_codebook_to_json("### Code Family: X\n")
        assert isinstance(out, str)
        # Must be valid, re-parseable JSON.
        json.loads(out)
