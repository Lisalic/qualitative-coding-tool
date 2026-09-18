"""Unit tests for backend/app/core/data_diff.py -- pure, synchronous
diffing logic over already-fetched id sets (the async DB read lives in
``version_service.diff_data``, tested at the route level in
``tests/backend/routes/test_version_routes.py::TestDiffData``).
"""

from backend.app.core.data_diff import SAMPLE_CAP, diff_row_ids


class TestDiffRowIds:
    def test_added_and_removed_are_symmetric_set_differences(self) -> None:
        diff = diff_row_ids(
            from_submission_ids={"s1", "s2", "s3"},
            to_submission_ids={"s2", "s3", "s4"},
            from_comment_ids=set(),
            to_comment_ids=set(),
        )
        assert diff.from_submissions == 3
        assert diff.to_submissions == 3
        assert diff.submissions_added == 1
        assert diff.submissions_removed == 1
        assert diff.sample_submissions_added == ["s4"]
        assert diff.sample_submissions_removed == ["s1"]

    def test_identical_sets_report_zero_change(self) -> None:
        diff = diff_row_ids(
            from_submission_ids={"s1"}, to_submission_ids={"s1"},
            from_comment_ids={"c1"}, to_comment_ids={"c1"},
        )
        assert diff.submissions_added == 0
        assert diff.submissions_removed == 0
        assert diff.comments_added == 0
        assert diff.comments_removed == 0
        assert diff.sample_submissions_added == []
        assert diff.sample_submissions_removed == []

    def test_empty_both_sides_is_empty(self) -> None:
        diff = diff_row_ids(
            from_submission_ids=set(), to_submission_ids=set(),
            from_comment_ids=set(), to_comment_ids=set(),
        )
        assert diff.is_empty()

    def test_nonempty_is_not_empty(self) -> None:
        diff = diff_row_ids(
            from_submission_ids=set(), to_submission_ids={"s1"},
            from_comment_ids=set(), to_comment_ids=set(),
        )
        assert not diff.is_empty()

    def test_sample_is_capped_and_sorted(self) -> None:
        to_ids = {f"s{i}" for i in range(SAMPLE_CAP + 20)}
        diff = diff_row_ids(
            from_submission_ids=set(), to_submission_ids=to_ids,
            from_comment_ids=set(), to_comment_ids=set(),
        )
        assert diff.submissions_added == SAMPLE_CAP + 20
        assert len(diff.sample_submissions_added) == SAMPLE_CAP
        assert diff.sample_submissions_added == sorted(diff.sample_submissions_added)

    def test_comments_tracked_independently_of_submissions(self) -> None:
        diff = diff_row_ids(
            from_submission_ids={"s1"}, to_submission_ids={"s1"},
            from_comment_ids={"c1", "c2"}, to_comment_ids={"c2"},
        )
        assert diff.submissions_added == 0
        assert diff.submissions_removed == 0
        assert diff.comments_removed == 1
        assert diff.sample_comments_removed == ["c1"]
