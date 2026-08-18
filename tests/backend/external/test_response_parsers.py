import pytest

from backend.app.external.response_parsers import parse_json_object, strip_markdown_fences


class TestStripMarkdownFences:
    def test_no_fences_unchanged(self) -> None:
        assert strip_markdown_fences("plain text") == "plain text"

    def test_strips_fenced_block(self) -> None:
        content = "```json\n{\"a\": 1}\n```"
        assert strip_markdown_fences(content) == '{"a": 1}'

    def test_strips_whitespace(self) -> None:
        assert strip_markdown_fences("  plain  ") == "plain"

    def test_empty_and_none_safe(self) -> None:
        assert strip_markdown_fences("") == ""
        assert strip_markdown_fences(None) == ""


class TestParseJsonObject:
    def test_parses_plain_json(self) -> None:
        assert parse_json_object('{"a": 1}') == {"a": 1}

    def test_parses_fenced_json(self) -> None:
        assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}

    def test_invalid_json_raises_error_cls(self) -> None:
        class MyError(Exception):
            pass

        with pytest.raises(MyError):
            parse_json_object("not json", error_cls=MyError)

    def test_non_dict_json_raises_error_cls(self) -> None:
        class MyError(Exception):
            pass

        with pytest.raises(MyError):
            parse_json_object("[1, 2, 3]", error_cls=MyError)

    def test_default_error_cls_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            parse_json_object("not json")
