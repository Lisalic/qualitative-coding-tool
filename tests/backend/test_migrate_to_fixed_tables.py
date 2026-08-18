"""Tests for backend/scripts/migrate_to_fixed_tables.py.

The script reads from the OLD per-artifact dynamic Postgres schema via
raw SQL against the sync `engine`, and writes into the NEW fixed tables
(`storage_models.Submission/Comment/ArtifactContent/CodingEntry`) via the
sync ORM `Session`. Real Postgres-specific behavior (`to_regclass`,
dynamic `CREATE SCHEMA`) can't be faithfully emulated by SQLite, so here
`backend.scripts.migrate_to_fixed_tables.engine` is monkeypatched to a
mock shaped like the raw SQL calls the script actually makes -- the same
pattern `tests/backend/routes/test_ai_and_raw_sql_routes.py`'s
`_mock_sync_engine` uses -- while `File`/`Submission`/`Comment`/
`ArtifactContent`/`CodingEntry` reads and writes go through the real
`db_session` fixture (in-memory SQLite).
"""

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.app.database import File, User
from backend.app.storage_models import ArtifactContent, CodingEntry, Comment, Submission
from backend.scripts.migrate_to_fixed_tables import (
    ALL_FILE_TYPES,
    CODING_FILE_TYPE,
    CONTENT_ONLY_FILE_TYPES,
    RAW_TABLE_FILE_TYPES,
    _parse_coding_entries,
    _word_count,
    build_arg_parser,
    format_reports,
    migrate_file_type,
)


# ---------------------------------------------------------------------------
# Mock engine for reads against the old dynamic per-artifact schema
# ---------------------------------------------------------------------------


def _make_mock_engine(fixtures: dict[str, dict[str, Any]]) -> MagicMock:
    """`fixtures`: schemaname -> {
        "tables": set of table names that exist in that schema,
        "submissions": list[dict] (rows for "submissions"),
        "comments": list[dict] (rows for "comments"),
        "content_text": str | None (row for "content_store"),
        "raise": Exception to raise on any query against this schema,
    }
    All keys optional; missing ones default to "nothing there".
    """
    conn = MagicMock()

    def _schema_for(sql: str, params: dict | None) -> str | None:
        if params and "tbl" in params:
            return params["tbl"].split(".")[0].strip('"')
        for name in fixtures:
            if f'"{name}"' in sql:
                return name
        return None

    def _execute(clause, params=None):
        sql = str(clause)
        schema = _schema_for(sql, params)
        fixture = fixtures.get(schema, {})
        if fixture.get("raise") is not None:
            raise fixture["raise"]

        result = MagicMock()
        if "to_regclass" in sql:
            tbl = (params or {}).get("tbl", "")
            table_name = tbl.split(".")[-1].strip('"')
            result.scalar.return_value = table_name if table_name in fixture.get("tables", set()) else None
        elif '"submissions"' in sql:
            result.mappings.return_value.all.return_value = fixture.get("submissions", [])
        elif '"comments"' in sql:
            result.mappings.return_value.all.return_value = fixture.get("comments", [])
        elif '"content_store"' in sql:
            result.scalar.return_value = fixture.get("content_text")
        else:
            raise AssertionError(f"unexpected SQL against mock engine: {sql}")
        return result

    conn.execute.side_effect = _execute

    @contextmanager
    def _connect():
        yield conn

    engine = MagicMock()
    engine.connect.side_effect = _connect
    return engine


def _make_user(db_session) -> User:
    user = User(email="owner@example.com", password="hash")
    db_session.add(user)
    db_session.commit()
    return user


def _make_file(db_session, user: User, *, file_type: str, schemaname: str, filename: str = "f") -> File:
    file = File(user_id=user.id, filename=filename, schemaname=schemaname, file_type=file_type)
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


CODING_BLOB = (
    "POST_ID: p1\n"
    "CODE: anxiety\n"
    'EVIDENCE: "felt nervous"\n'
    "CODE: hope\n"
    'EVIDENCE: "things will improve"\n'
    "\n"
    "POST_ID: p2\n"
    "CODE: anxiety\n"
    'EVIDENCE: "worried sick"\n'
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestWordCount:
    def test_none_is_zero(self) -> None:
        assert _word_count(None) == 0

    def test_empty_string_is_zero(self) -> None:
        assert _word_count("") == 0

    def test_whitespace_only_is_zero(self) -> None:
        assert _word_count("   \n\t  ") == 0

    def test_counts_tokens(self) -> None:
        assert _word_count("hello world") == 2

    def test_collapses_internal_whitespace(self) -> None:
        assert _word_count("hello   world\nfoo") == 3


class TestParseCodingEntries:
    def test_multi_post_multi_code(self) -> None:
        rows = _parse_coding_entries(CODING_BLOB)
        assert len(rows) == 3
        by_key = {(r["post_id"], r["code"]): r["evidence"] for r in rows}
        assert by_key[("p1", "anxiety")] == '"felt nervous"'
        assert by_key[("p1", "hope")] == '"things will improve"'
        assert by_key[("p2", "anxiety")] == '"worried sick"'

    def test_no_records_returns_empty_list(self) -> None:
        assert _parse_coding_entries("not in the expected format at all") == []

    def test_duplicate_post_code_pair_merges_evidence(self) -> None:
        blob = (
            "POST_ID: p1\n"
            "CODE: anxiety\n"
            'EVIDENCE: "first snippet"\n'
            "\n"
            "POST_ID: p1\n"
            "CODE: anxiety\n"
            'EVIDENCE: "second snippet"\n'
        )
        rows = _parse_coding_entries(blob)
        assert len(rows) == 1
        assert rows[0]["post_id"] == "p1"
        assert rows[0]["code"] == "anxiety"
        assert "first snippet" in rows[0]["evidence"]
        assert "second snippet" in rows[0]["evidence"]


class TestBuildArgParser:
    def test_no_file_type_yields_none(self) -> None:
        args = build_arg_parser().parse_args([])
        assert args.file_types is None

    def test_single_file_type(self) -> None:
        args = build_arg_parser().parse_args(["--file-type", "raw_data"])
        assert args.file_types == ["raw_data"]

    def test_repeated_file_type_accumulates(self) -> None:
        args = build_arg_parser().parse_args(
            ["--file-type", "raw_data", "--file-type", "codebook"]
        )
        assert args.file_types == ["raw_data", "codebook"]

    def test_invalid_file_type_rejected(self) -> None:
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args(["--file-type", "not_a_real_type"])

    def test_all_file_types_are_valid_choices(self) -> None:
        for file_type in ALL_FILE_TYPES:
            args = build_arg_parser().parse_args(["--file-type", file_type])
            assert args.file_types == [file_type]


# ---------------------------------------------------------------------------
# raw_data / filtered_data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("file_type", RAW_TABLE_FILE_TYPES)
class TestMigrateRawTableFileTypes:
    def test_happy_path_copies_submissions_and_comments(
        self, db_session, monkeypatch, file_type
    ) -> None:
        user = _make_user(db_session)
        file = _make_file(db_session, user, file_type=file_type, schemaname="proj_abc123")

        engine = _make_mock_engine(
            {
                "proj_abc123": {
                    "tables": {"submissions", "comments"},
                    "submissions": [
                        {
                            "id": "s1",
                            "subreddit": "test",
                            "title": "Hello",
                            "selftext": "world",
                            "author": "a",
                            "created_utc": 100,
                            "score": 5,
                            "num_comments": 1,
                        }
                    ],
                    "comments": [
                        {
                            "id": "c1",
                            "subreddit": "test",
                            "body": "a reply here",
                            "author": "b",
                            "created_utc": 101,
                            "score": 2,
                            "link_id": "s1",
                            "parent_id": "s1",
                        }
                    ],
                }
            }
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, file_type)

        assert report.files_processed == 1
        assert report.files_migrated == 1
        assert report.files_skipped == 0
        assert report.files_errored == 0
        assert report.rows_copied["submissions"] == 1
        assert report.rows_copied["comments"] == 1

        sub = db_session.query(Submission).filter(Submission.file_id == file.id).one()
        assert sub.id == "s1"
        assert sub.word_count == 2  # "Hello world" -> 2 tokens

        com = db_session.query(Comment).filter(Comment.file_id == file.id).one()
        assert com.id == "c1"
        assert com.word_count == 3  # "a reply here" -> 3 tokens

    def test_missing_tables_result_in_zero_rows_not_an_error(
        self, db_session, monkeypatch, file_type
    ) -> None:
        user = _make_user(db_session)
        _make_file(db_session, user, file_type=file_type, schemaname="proj_empty")

        engine = _make_mock_engine({"proj_empty": {"tables": set()}})
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, file_type)

        assert report.files_migrated == 1
        assert report.files_errored == 0
        assert report.rows_copied["submissions"] == 0
        assert report.rows_copied["comments"] == 0

    def test_idempotent_rerun_does_not_duplicate_rows(
        self, db_session, monkeypatch, file_type
    ) -> None:
        user = _make_user(db_session)
        file = _make_file(db_session, user, file_type=file_type, schemaname="proj_dup")

        engine = _make_mock_engine(
            {
                "proj_dup": {
                    "tables": {"submissions", "comments"},
                    "submissions": [
                        {
                            "id": "s1",
                            "subreddit": "test",
                            "title": "a",
                            "selftext": "b",
                            "author": "x",
                            "created_utc": 1,
                            "score": 0,
                            "num_comments": 0,
                        }
                    ],
                    "comments": [
                        {
                            "id": "c1",
                            "subreddit": "test",
                            "body": "hi",
                            "author": "x",
                            "created_utc": 1,
                            "score": 0,
                            "link_id": "s1",
                            "parent_id": "s1",
                        }
                    ],
                }
            }
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report1 = migrate_file_type(db_session, file_type)
        assert report1.files_migrated == 1

        report2 = migrate_file_type(db_session, file_type)
        assert report2.files_migrated == 0
        assert report2.files_skipped == 1

        assert db_session.query(Submission).filter(Submission.file_id == file.id).count() == 1
        assert db_session.query(Comment).filter(Comment.file_id == file.id).count() == 1

    def test_unreadable_schema_is_logged_and_does_not_abort_run(
        self, db_session, monkeypatch, file_type
    ) -> None:
        user = _make_user(db_session)
        bad_file = _make_file(db_session, user, file_type=file_type, schemaname="proj_bad", filename="bad")
        good_file = _make_file(db_session, user, file_type=file_type, schemaname="proj_good", filename="good")

        engine = _make_mock_engine(
            {
                "proj_bad": {"raise": Exception("relation does not exist")},
                "proj_good": {
                    "tables": {"submissions"},
                    "submissions": [
                        {
                            "id": "s1",
                            "subreddit": "t",
                            "title": "x",
                            "selftext": "y",
                            "author": "a",
                            "created_utc": 1,
                            "score": 0,
                            "num_comments": 0,
                        }
                    ],
                },
            }
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, file_type)

        assert report.files_processed == 2
        assert report.files_errored == 1
        assert report.files_migrated == 1
        assert len(report.errors) == 1
        assert report.errors[0].file_id == bad_file.id

        assert db_session.query(Submission).filter(Submission.file_id == good_file.id).count() == 1
        assert db_session.query(Submission).filter(Submission.file_id == bad_file.id).count() == 0


# ---------------------------------------------------------------------------
# codebook / codebook_comparison / summary / coding_comparison
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("file_type", CONTENT_ONLY_FILE_TYPES)
class TestMigrateContentOnlyFileTypes:
    def test_happy_path_copies_content(self, db_session, monkeypatch, file_type) -> None:
        user = _make_user(db_session)
        file = _make_file(db_session, user, file_type=file_type, schemaname="cmp_abc")

        engine = _make_mock_engine(
            {"cmp_abc": {"tables": {"content_store"}, "content_text": "hello world content"}}
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, file_type)

        assert report.files_migrated == 1
        assert report.files_errored == 0
        assert report.rows_copied["artifact_content"] == 1

        row = db_session.query(ArtifactContent).filter(ArtifactContent.file_id == file.id).one()
        assert row.content == "hello world content"

    def test_missing_content_store_is_an_error_and_does_not_abort_run(
        self, db_session, monkeypatch, file_type
    ) -> None:
        user = _make_user(db_session)
        bad_file = _make_file(db_session, user, file_type=file_type, schemaname="cmp_missing")
        good_file = _make_file(db_session, user, file_type=file_type, schemaname="cmp_good")

        engine = _make_mock_engine(
            {
                "cmp_missing": {"tables": set()},
                "cmp_good": {"tables": {"content_store"}, "content_text": "ok"},
            }
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, file_type)

        assert report.files_errored == 1
        assert report.files_migrated == 1
        assert db_session.query(ArtifactContent).filter(ArtifactContent.file_id == good_file.id).count() == 1
        assert db_session.query(ArtifactContent).filter(ArtifactContent.file_id == bad_file.id).count() == 0

    def test_idempotent_rerun_does_not_duplicate(self, db_session, monkeypatch, file_type) -> None:
        user = _make_user(db_session)
        file = _make_file(db_session, user, file_type=file_type, schemaname="cmp_dup")

        engine = _make_mock_engine(
            {"cmp_dup": {"tables": {"content_store"}, "content_text": "text"}}
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        migrate_file_type(db_session, file_type)
        report2 = migrate_file_type(db_session, file_type)

        assert report2.files_skipped == 1
        assert report2.files_migrated == 0
        assert db_session.query(ArtifactContent).filter(ArtifactContent.file_id == file.id).count() == 1


# ---------------------------------------------------------------------------
# coding -- content_store blob + structured coding_entries re-parse
# ---------------------------------------------------------------------------


class TestMigrateCodingFileType:
    def test_happy_path_copies_content_and_structured_entries(self, db_session, monkeypatch) -> None:
        user = _make_user(db_session)
        file = _make_file(db_session, user, file_type=CODING_FILE_TYPE, schemaname="proj_coding1")

        engine = _make_mock_engine(
            {"proj_coding1": {"tables": {"content_store", "codebook"}, "content_text": CODING_BLOB}}
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, CODING_FILE_TYPE)

        assert report.files_migrated == 1
        assert report.files_errored == 0
        assert report.rows_copied["artifact_content"] == 1
        assert report.rows_copied["coding_entries"] == 3

        content_row = db_session.query(ArtifactContent).filter(ArtifactContent.file_id == file.id).one()
        assert content_row.content == CODING_BLOB

        entries = db_session.query(CodingEntry).filter(CodingEntry.file_id == file.id).all()
        assert len(entries) == 3
        codes = {(e.post_id, e.code) for e in entries}
        assert codes == {("p1", "anxiety"), ("p1", "hope"), ("p2", "anxiety")}

    def test_does_not_copy_the_redundant_parent_codebook_table(self, db_session, monkeypatch) -> None:
        """The old schema's `codebook` table (a redundant copy of the
        parent codebook's text, already reachable via file_dependencies)
        must never be queried or copied -- only `content_store`.
        """
        user = _make_user(db_session)
        _make_file(db_session, user, file_type=CODING_FILE_TYPE, schemaname="proj_coding2")

        engine = _make_mock_engine(
            {
                "proj_coding2": {
                    "tables": {"content_store"},  # "codebook" deliberately absent
                    "content_text": CODING_BLOB,
                }
            }
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, CODING_FILE_TYPE)

        assert report.files_migrated == 1
        assert report.files_errored == 0

    def test_malformed_blob_logs_and_continues_without_crashing(self, db_session, monkeypatch) -> None:
        user = _make_user(db_session)
        file = _make_file(db_session, user, file_type=CODING_FILE_TYPE, schemaname="proj_coding3")

        engine = _make_mock_engine(
            {"proj_coding3": {"tables": {"content_store"}, "content_text": "totally not the expected format"}}
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, CODING_FILE_TYPE)

        # Content still gets copied even though no structured records parse out.
        assert report.files_migrated == 1
        assert report.rows_copied["artifact_content"] == 1
        assert report.rows_copied["coding_entries"] == 0
        assert db_session.query(ArtifactContent).filter(ArtifactContent.file_id == file.id).count() == 1
        assert db_session.query(CodingEntry).filter(CodingEntry.file_id == file.id).count() == 0

    def test_idempotent_rerun_does_not_duplicate(self, db_session, monkeypatch) -> None:
        user = _make_user(db_session)
        file = _make_file(db_session, user, file_type=CODING_FILE_TYPE, schemaname="proj_coding4")

        engine = _make_mock_engine(
            {"proj_coding4": {"tables": {"content_store"}, "content_text": CODING_BLOB}}
        )
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        migrate_file_type(db_session, CODING_FILE_TYPE)
        report2 = migrate_file_type(db_session, CODING_FILE_TYPE)

        assert report2.files_skipped == 1
        assert report2.files_migrated == 0
        assert db_session.query(ArtifactContent).filter(ArtifactContent.file_id == file.id).count() == 1
        assert db_session.query(CodingEntry).filter(CodingEntry.file_id == file.id).count() == 3


# ---------------------------------------------------------------------------
# Report formatting / no-op behaviour
# ---------------------------------------------------------------------------


class TestReportFormatting:
    def test_no_files_of_type_yields_empty_report(self, db_session, monkeypatch) -> None:
        engine = _make_mock_engine({})
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        report = migrate_file_type(db_session, "raw_data")

        assert report.files_processed == 0
        assert report.files_migrated == 0
        assert "raw_data" in report.format()

    def test_format_reports_joins_multiple_reports(self, db_session, monkeypatch) -> None:
        engine = _make_mock_engine({})
        monkeypatch.setattr("backend.scripts.migrate_to_fixed_tables.engine", engine)

        reports = [migrate_file_type(db_session, "raw_data"), migrate_file_type(db_session, "codebook")]
        text = format_reports(reports)
        assert "file_type=raw_data" in text
        assert "file_type=codebook" in text
