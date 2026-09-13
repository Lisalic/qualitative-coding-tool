"""Unit tests for backend/app/services/export_service.py.

Validates deterministic, RFC 4180 compliant CSV and JSON exports for codebooks,
coding entries, row memos, and frequency summaries. Covers owner scoping,
historical versions, empty artifacts, and format validity.
"""

import json
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import File, User
from backend.app.services import export_service, version_service
from backend.app.storage_models import CodingEntry, RowMemo


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture()
async def session(SessionLocal):
    async with SessionLocal() as s:
        yield s


@pytest.fixture()
async def user_id(session) -> int:
    user = User(email="export-service-test@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


@pytest.fixture()
async def other_user_id(session) -> int:
    user = User(email="export-other-user@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


async def _make_file(session, owner_id: int, filename: str, file_type: str) -> File:
    file_rec = File(
        user_id=owner_id,
        filename=filename,
        schemaname="test_schema",
        file_type=file_type,
    )
    session.add(file_rec)
    await session.commit()
    await session.refresh(file_rec)
    return file_rec


def _make_code_row(code_uid: str, name: str, position: int = 1, family_uid: str = "", family_name: str = "", **kwargs) -> dict:
    row = {
        "code_uid": code_uid,
        "name": name,
        "position": position,
        "family_uid": family_uid,
        "family_name": family_name,
        "body": kwargs.get("body", name),
        "definition": kwargs.get("definition", ""),
        "inclusion": kwargs.get("inclusion", ""),
        "exclusion": kwargs.get("exclusion", ""),
        "keywords": kwargs.get("keywords", ""),
        "example": kwargs.get("example", ""),
    }
    return row


@pytest.mark.asyncio
async def test_export_codebook_empty(session, user_id):
    file_rec = await _make_file(session, user_id, "my_cb.csv", "codebook")
    await version_service.commit_codebook_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin="manual", codes=[]
    )

    csv_out, media, filename = await export_service.export_codebook(
        session, file_rec.id, user_id, export_format="csv"
    )
    assert media == "text/csv; charset=utf-8"
    assert "code_uid,name,family_uid,family_name" in csv_out
    assert filename == "my_cb_v1_codebook.csv"

    json_out, media_j, filename_j = await export_service.export_codebook(
        session, file_rec.id, user_id, export_format="json"
    )
    assert media_j == "application/json; charset=utf-8"
    data = json.loads(json_out)
    assert data["file_id"] == file_rec.id
    assert data["codes"] == []
    assert filename_j == "my_cb_v1_codebook.json"


@pytest.mark.asyncio
async def test_export_codebook_with_codes(session, user_id):
    file_rec = await _make_file(session, user_id, "codes.csv", "codebook")
    codes = [
        _make_code_row("c2", "Beta", position=2, family_uid="f1", family_name="Fam"),
        _make_code_row("c1", "Alpha", position=1, family_uid="f1", family_name="Fam"),
    ]
    await version_service.commit_codebook_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin="manual", codes=codes
    )

    csv_out, _, _ = await export_service.export_codebook(session, file_rec.id, user_id, export_format="csv")
    lines = csv_out.strip().split("\r\n")
    assert len(lines) == 3  # header + 2 codes
    # Ordered by position (c1 then c2)
    assert lines[1].startswith("c1,Alpha")
    assert lines[2].startswith("c2,Beta")

    json_out, _, _ = await export_service.export_codebook(session, file_rec.id, user_id, export_format="json")
    data = json.loads(json_out)
    assert len(data["codes"]) == 2
    assert data["codes"][0]["code_uid"] == "c1"
    assert data["codes"][1]["code_uid"] == "c2"


@pytest.mark.asyncio
async def test_export_codebook_historical_version(session, user_id):
    file_rec = await _make_file(session, user_id, "hist_cb.csv", "codebook")
    v1_codes = [_make_code_row("c1", "V1 Code", position=1)]
    await version_service.commit_codebook_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin="manual", codes=v1_codes
    )
    v2_codes = [
        _make_code_row("c1", "V1 Code", position=1),
        _make_code_row("c2", "V2 Code", position=2),
    ]
    await version_service.commit_codebook_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin="manual", codes=v2_codes
    )

    csv_v1, _, filename_v1 = await export_service.export_codebook(
        session, file_rec.id, user_id, version_no=1, export_format="csv"
    )
    assert "V2 Code" not in csv_v1
    assert "V1 Code" in csv_v1
    assert filename_v1 == "hist_cb_v1_codebook.csv"

    csv_v2, _, filename_v2 = await export_service.export_codebook(
        session, file_rec.id, user_id, version_no=2, export_format="csv"
    )
    assert "V2 Code" in csv_v2
    assert filename_v2 == "hist_cb_v2_codebook.csv"


@pytest.mark.asyncio
async def test_export_codebook_unauthorized_and_type_check(session, user_id, other_user_id):
    cb = await _make_file(session, user_id, "my_cb.csv", "codebook")
    with pytest.raises(NotFoundError):
        await export_service.export_codebook(session, cb.id, other_user_id)

    non_cb = await _make_file(session, user_id, "data.csv", "dataset")
    with pytest.raises(ValidationAppError):
        await export_service.export_codebook(session, non_cb.id, user_id)


@pytest.mark.asyncio
async def test_export_coding_with_entries(session, user_id):
    coding_file = await _make_file(session, user_id, "coded_data.csv", "coding")
    await version_service.commit_coding_version(
        session, file_id=coding_file.id, author_user_id=user_id, origin="manual"
    )

    entry = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="post_100",
        code="Theme Alpha",
        code_uid="uid_alpha",
        quote="A memorable quote",
        start_offset=10,
        end_offset=27,
        notes="Important note",
        coder="human",
        valid_from=1,
        valid_to=None,
    )
    session.add(entry)
    await session.commit()

    csv_out, media, filename = await export_service.export_coding(
        session, coding_file.id, user_id, export_format="csv"
    )
    assert media == "text/csv; charset=utf-8"
    assert "entry_id,row_type,post_id,code_uid,code,quote" in csv_out
    assert "A memorable quote" in csv_out
    assert "post_100" in csv_out
    assert filename == "coded_data_v1_coding.csv"

    json_out, media_j, filename_j = await export_service.export_coding(
        session, coding_file.id, user_id, export_format="json"
    )
    assert media_j == "application/json; charset=utf-8"
    data = json.loads(json_out)
    assert data["file_id"] == coding_file.id
    assert len(data["entries"]) == 1
    assert data["entries"][0]["quote"] == "A memorable quote"
    assert data["entries"][0]["notes"] == "Important note"
    assert filename_j == "coded_data_v1_coding.json"


@pytest.mark.asyncio
async def test_export_memos(session, user_id):
    coding_file = await _make_file(session, user_id, "coded_data.csv", "coding")
    memo = RowMemo(
        file_id=coding_file.id,
        row_type="submission",
        row_id="post_100",
        body="Analytic memo for post 100",
        author_user_id=user_id,
    )
    session.add(memo)
    await session.commit()

    csv_out, media, filename = await export_service.export_memos(
        session, coding_file.id, user_id, export_format="csv"
    )
    assert "memo_id,row_type,row_id,body" in csv_out
    assert "Analytic memo for post 100" in csv_out
    assert filename == "coded_data_memos.csv"

    json_out, _, filename_j = await export_service.export_memos(
        session, coding_file.id, user_id, export_format="json"
    )
    data = json.loads(json_out)
    assert len(data["memos"]) == 1
    assert data["memos"][0]["body"] == "Analytic memo for post 100"
    assert filename_j == "coded_data_memos.json"


@pytest.mark.asyncio
async def test_export_summary(session, user_id):
    coding_file = await _make_file(session, user_id, "coded_data.csv", "coding")
    e1 = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="p1",
        code="Theme B",
        code_uid="b",
        quote="q1",
        start_offset=0,
        end_offset=2,
    )
    e2 = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="p2",
        code="Theme A",
        code_uid="a",
        quote="q2",
        start_offset=0,
        end_offset=2,
    )
    e3 = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="p3",
        code="Theme A",
        code_uid="a",
        quote="q3",
        start_offset=0,
        end_offset=2,
    )
    session.add_all([e1, e2, e3])
    await session.commit()

    csv_out, _, filename = await export_service.export_summary(
        session, coding_file.id, user_id, export_format="csv"
    )
    lines = csv_out.strip().split("\r\n")
    assert lines[0] == "code,frequency"
    assert lines[1] == "Theme A,2"
    assert lines[2] == "Theme B,1"
    assert filename == "coded_data_summary.csv"

    json_out, _, _ = await export_service.export_summary(
        session, coding_file.id, user_id, export_format="json"
    )
    data = json.loads(json_out)
    assert data["summary"] == [
        {"code": "Theme A", "frequency": 2},
        {"code": "Theme B", "frequency": 1},
    ]


@pytest.mark.asyncio
async def test_repeated_exports_are_byte_identical(session, user_id):
    """Exports of unchanged data must produce byte-identical output (QC-001)."""
    coding_file = await _make_file(session, user_id, "repeat_test.csv", "coding")
    await version_service.commit_coding_version(
        session, file_id=coding_file.id, author_user_id=user_id, origin="manual"
    )
    e1 = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="p1",
        code="Theme A",
        code_uid="a",
        quote="q1",
        start_offset=0,
        end_offset=2,
        valid_from=1,
        valid_to=None,
    )
    memo = RowMemo(
        file_id=coding_file.id,
        row_type="submission",
        row_id="p1",
        body="Note",
        author_user_id=user_id,
    )
    session.add_all([e1, memo])
    await session.commit()

    # Repeated coding JSON exports
    c1, _, _ = await export_service.export_coding(session, coding_file.id, user_id, export_format="json")
    c2, _, _ = await export_service.export_coding(session, coding_file.id, user_id, export_format="json")
    assert c1 == c2

    # Repeated summary JSON exports
    s1, _, _ = await export_service.export_summary(session, coding_file.id, user_id, export_format="json")
    s2, _, _ = await export_service.export_summary(session, coding_file.id, user_id, export_format="json")
    assert s1 == s2

    # Repeated memo JSON exports
    m1, _, _ = await export_service.export_memos(session, coding_file.id, user_id, export_format="json")
    m2, _, _ = await export_service.export_memos(session, coding_file.id, user_id, export_format="json")
    assert m1 == m2


@pytest.mark.asyncio
async def test_export_summary_with_historical_version(session, user_id):
    """Historical summary exports respect entries_as_of version_no (QC-001)."""
    coding_file = await _make_file(session, user_id, "hist_summary.csv", "coding")
    await version_service.commit_coding_version(
        session, file_id=coding_file.id, author_user_id=user_id, origin="manual"
    )
    # Version 1 entry: Theme A (valid_from=1, valid_to=1)
    e_v1 = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="p1",
        code="Theme A",
        code_uid="a",
        quote="q1",
        start_offset=0,
        end_offset=2,
        valid_from=1,
        valid_to=1,
    )
    # Version 2 entries: Theme B (valid_from=2, valid_to=None), Theme B (valid_from=2, valid_to=None)
    e_v2_1 = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="p1",
        code="Theme B",
        code_uid="b",
        quote="q1",
        start_offset=0,
        end_offset=2,
        valid_from=2,
        valid_to=None,
    )
    e_v2_2 = CodingEntry(
        file_id=coding_file.id,
        row_type="submission",
        post_id="p2",
        code="Theme B",
        code_uid="b",
        quote="q2",
        start_offset=0,
        end_offset=2,
        valid_from=2,
        valid_to=None,
    )
    session.add_all([e_v1, e_v2_1, e_v2_2])
    await session.commit()
    await version_service.commit_coding_version(
        session, file_id=coding_file.id, author_user_id=user_id, origin="manual"
    )

    # Historical summary for version 1
    json_v1, _, fn_v1 = await export_service.export_summary(
        session, coding_file.id, user_id, version_no=1, export_format="json"
    )
    data_v1 = json.loads(json_v1)
    assert data_v1["version_no"] == 1
    assert data_v1["summary"] == [{"code": "Theme A", "frequency": 1}]
    assert fn_v1 == "hist_summary_v1_summary.json"

    # Historical summary for version 2
    json_v2, _, fn_v2 = await export_service.export_summary(
        session, coding_file.id, user_id, version_no=2, export_format="json"
    )
    data_v2 = json.loads(json_v2)
    assert data_v2["version_no"] == 2
    assert data_v2["summary"] == [{"code": "Theme B", "frequency": 2}]
    assert fn_v2 == "hist_summary_v2_summary.json"
