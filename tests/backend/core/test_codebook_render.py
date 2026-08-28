"""Tests for backend/app/core/codebook_render.py -- JSON/markdown <-> rows."""

import json

import pytest

from backend.app.core.codebook_render import (
    materialize_fields_from_body,
    parse_json_to_codes,
    parse_markdown_to_codes,
    render_codes_to_markdown,
)


def _json_payload(codes: list[dict]) -> str:
    return json.dumps({"codes": codes})


def _full_code(**overrides) -> dict:
    row = {
        "family": "Anxiety",
        "name": "Panic",
        "definition": "a def",
        "inclusion": "when to use",
        "exclusion": "when not",
        "keywords": "panic, fear",
        "example": "I couldn't breathe",
    }
    row.update(overrides)
    return row


class TestParseJsonToCodes:
    def test_fills_structured_fields_and_reconstructs_body(self) -> None:
        rows = parse_json_to_codes(_json_payload([_full_code()]))
        assert len(rows) == 1
        row = rows[0]
        assert row["family_name"] == "Anxiety"
        assert row["name"] == "Panic"
        assert row["definition"] == "a def"
        assert row["inclusion"] == "when to use"
        assert row["exclusion"] == "when not"
        assert row["keywords"] == "panic, fear"
        assert row["example"] == "I couldn't breathe"
        assert "Definition: a def" in row["body"]
        assert "Exclusion Criteria: when not" in row["body"]

    def test_drops_codes_missing_family_or_name(self) -> None:
        rows = parse_json_to_codes(
            _json_payload(
                [
                    _full_code(name=""),
                    {"family": "", "name": "X"},
                    _full_code(name="Kept"),
                ]
            )
        )
        assert [r["name"] for r in rows] == ["Kept"]

    def test_consecutive_same_family_share_uid_later_repeat_does_not(self) -> None:
        rows = parse_json_to_codes(
            _json_payload(
                [
                    _full_code(family="A", name="One"),
                    _full_code(family="A", name="Two"),
                    _full_code(family="B", name="Three"),
                    _full_code(family="A", name="Four"),
                ]
            )
        )
        assert rows[0]["family_uid"] == rows[1]["family_uid"]
        assert rows[0]["family_uid"] != rows[2]["family_uid"]
        assert rows[3]["family_uid"] != rows[0]["family_uid"]

    def test_existing_preserves_uids_by_family_and_name(self) -> None:
        first = parse_json_to_codes(_json_payload([_full_code()]))
        again = parse_json_to_codes(_json_payload([_full_code()]), existing=first)
        assert again[0]["code_uid"] == first[0]["code_uid"]
        assert again[0]["family_uid"] == first[0]["family_uid"]

    def test_not_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_json_to_codes("not json")

    def test_missing_codes_key_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_json_to_codes('{"not_codes": []}')


class TestParseMarkdownToCodes:
    def test_splits_labeled_fields_out_of_body(self) -> None:
        raw = (
            "### Code Family: Anxiety\n"
            "#### Code Name: Panic\n"
            "Definition: a def\n"
            "Inclusion Criteria: when to use\n"
            "Exclusion Criteria: when not\n"
            "Key Words: panic, fear\n"
            "Example: I couldn't breathe\n"
        )
        rows = parse_markdown_to_codes(raw)
        assert rows[0]["definition"] == "a def"
        assert rows[0]["inclusion"] == "when to use"
        assert rows[0]["exclusion"] == "when not"
        assert rows[0]["keywords"] == "panic, fear"
        assert rows[0]["example"] == "I couldn't breathe"

    def test_unlabeled_prose_becomes_definition(self) -> None:
        raw = "### Code Family: F\n#### Code Name: C\njust some prose\n"
        rows = parse_markdown_to_codes(raw)
        assert rows[0]["definition"] == "just some prose"
        assert rows[0]["inclusion"] is None
        assert "Definition: just some prose" in rows[0]["body"]


class TestMaterializeFieldsFromBody:
    def test_splits_labels(self) -> None:
        fields = materialize_fields_from_body("Definition: a def\nInclusion Criteria: when")
        assert fields["definition"] == "a def"
        assert fields["inclusion"] == "when"
        assert "Definition: a def" in (fields["body"] or "")

    def test_markdown_bold_labels(self) -> None:
        fields = materialize_fields_from_body(
            "**Definition:** a def\n**Inclusion Criteria:** when\n**Key Words:** kw\n**Example:** quote"
        )
        assert fields["definition"] == "a def"
        assert fields["inclusion"] == "when"
        assert fields["keywords"] == "kw"
        assert fields["example"] == "quote"

    def test_strips_nested_definition_prefix_from_a_prior_pass(self) -> None:
        fields = materialize_fields_from_body(
            "Definition: **Definition:** a def\n**Inclusion Criteria:** when"
        )
        assert fields["definition"] == "a def"
        assert fields["inclusion"] == "when"


class TestRenderCodesToMarkdown:
    def test_emits_labeled_fields_when_structured(self) -> None:
        rows = parse_json_to_codes(_json_payload([_full_code()]))
        md = render_codes_to_markdown(rows)
        assert "### Code Family: Anxiety" in md
        assert "#### Code Name: Panic" in md
        assert "Definition: a def" in md
        assert "Inclusion Criteria: when to use" in md
        assert "Exclusion Criteria: when not" in md

    def test_emits_definition_for_unlabeled_prose(self) -> None:
        rows = parse_markdown_to_codes("### Code Family: F\n#### Code Name: C\njust some prose\n")
        md = render_codes_to_markdown(rows)
        assert "Definition: just some prose" in md

    def test_json_to_markdown_to_rows_keeps_fields(self) -> None:
        original = parse_json_to_codes(_json_payload([_full_code()]))
        md = render_codes_to_markdown(original)
        round_tripped = parse_markdown_to_codes(md)
        for key in ("name", "family_name", "definition", "inclusion", "exclusion", "keywords", "example"):
            assert round_tripped[0][key] == original[0][key]
