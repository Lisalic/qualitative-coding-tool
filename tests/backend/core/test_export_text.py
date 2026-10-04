"""Unit tests for backend/app/core/export_text.py -- the sanitizers every
export writer runs user text through."""

import pytest

from backend.app.core.export_text import md_inline, neutralize_formula, xml_safe


class TestNeutralizeFormula:
    @pytest.mark.parametrize(
        "payload",
        [
            '=HYPERLINK("http://x","y")',
            "+1 agree",
            "-cmd",
            "@SUM(A1)",
            ' =HYPERLINK("http://x")',
            "\n=1+1",
            "\t=1+1",
            "\r=1+1",
            "   +1",
        ],
    )
    def test_prefixes_anything_a_spreadsheet_would_evaluate(self, payload: str) -> None:
        assert neutralize_formula(payload) == "'" + payload

    @pytest.mark.parametrize("value", ["plain text", "a = b", "email@example.com", "", "100%"])
    def test_leaves_ordinary_text_alone(self, value: str) -> None:
        assert neutralize_formula(value) == value


class TestXmlSafe:
    def test_strips_characters_xml_forbids(self) -> None:
        assert xml_safe("a\x0bb\x00c\x1fd￾e￿") == "abcde"

    def test_strips_lone_surrogates(self) -> None:
        assert xml_safe("x\ud800y\udfffz") == "xyz"

    def test_keeps_tab_newline_carriage_return_and_unicode(self) -> None:
        assert xml_safe("a\tb\nc\rd — ☃ 日本") == "a\tb\nc\rd — ☃ 日本"

    def test_none_is_empty(self) -> None:
        assert xml_safe(None) == ""


class TestMdInline:
    def test_flattens_newlines_so_a_heading_cannot_start_a_new_block(self) -> None:
        assert md_inline("name\n# injected heading") == "name # injected heading"

    def test_neutralizes_raw_html(self) -> None:
        assert md_inline("<script>alert(1)</script>") == "\\<script\\>alert(1)\\</script\\>"

    def test_escapes_pipes_and_backslashes(self) -> None:
        assert md_inline("a|b\\c") == "a\\|b\\\\c"

    @pytest.mark.parametrize(
        "value,expected",
        [("# not a heading", "\\# not a heading"), ("- item", "\\- item"), ("1. first", "1\\. first")],
    )
    def test_escapes_a_leading_block_marker(self, value: str, expected: str) -> None:
        assert md_inline(value) == expected

    @pytest.mark.parametrize("value", ["-3", "3.5", "#hashtag", "Theme A"])
    def test_leaves_values_that_cannot_open_a_block(self, value: str) -> None:
        assert md_inline(value) == value
