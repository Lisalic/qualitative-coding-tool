import pytest

from backend.app.core.item_types import (
    COMMENT,
    SUBMISSION,
    qualify_item_id,
    split_item_id,
)


class TestQualifyItemId:
    def test_submission_gets_t3_prefix(self) -> None:
        assert qualify_item_id(SUBMISSION, "abc123") == "t3_abc123"

    def test_comment_gets_t1_prefix(self) -> None:
        assert qualify_item_id(COMMENT, "xyz789") == "t1_xyz789"

    def test_unknown_row_type_raises(self) -> None:
        with pytest.raises(ValueError):
            qualify_item_id("reply", "abc123")


class TestSplitItemId:
    def test_round_trips_a_qualified_submission_id(self) -> None:
        assert split_item_id(qualify_item_id(SUBMISSION, "abc123")) == (SUBMISSION, "abc123")

    def test_round_trips_a_qualified_comment_id(self) -> None:
        assert split_item_id(qualify_item_id(COMMENT, "xyz789")) == (COMMENT, "xyz789")

    def test_unprefixed_id_defaults_to_submission(self) -> None:
        # Every artifact saved before item types existed only ever
        # contains bare ids -- this default is what keeps them meaning
        # exactly what they always meant.
        assert split_item_id("abc123") == (SUBMISSION, "abc123")

    def test_empty_string_defaults_to_submission(self) -> None:
        assert split_item_id("") == (SUBMISSION, "")

    def test_none_defaults_to_submission_with_empty_id(self) -> None:
        assert split_item_id(None) == (SUBMISSION, "")
