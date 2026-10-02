"""Unit tests for backend/app/api/export_routes.py.

Validates export endpoints (/api/export/{ref}/...), ensuring authentication,
owner scoping, HTTP headers, and Content-Disposition attachments.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import File, User
from backend.app.services import version_service
from backend.app.storage_models import CodingEntry, RowMemo

pytestmark = pytest.mark.usefixtures("override_async_db")


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session_factory, email: str = "export_route_test@example.com") -> User:
    async with session_factory() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_file(session_factory, user_id: int, filename: str, file_type: str) -> File:
    async with session_factory() as session:
        file_rec = File(
            user_id=user_id,
            filename=filename,
            schemaname=filename.replace(".", "_"),
            file_type=file_type,
        )
        session.add(file_rec)
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


def test_export_unauthenticated_rejected(client):
    resp = client.get("/api/export/999/codebook")
    assert resp.status_code == 401


async def test_export_unowned_file_rejected(client, session_factory, make_token):
    user_a = await _make_user(session_factory, "user_a@example.com")
    user_b = await _make_user(session_factory, "user_b@example.com")
    file_a = await _make_file(session_factory, user_a.id, "cb.csv", "codebook")

    resp = client.get(
        f"/api/export/{file_a.id}/codebook",
        cookies={"access_token": make_token(sub=str(user_b.id))},
    )
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "file_type,export_path",
    [
        ("codebook", "codebook"),
        ("coding", "coding"),
        ("coding", "memos"),
        ("coding", "summary"),
    ],
)
async def test_export_unowned_file_rejected_on_every_file_scoped_route(
    client, session_factory, make_token, file_type, export_path
):
    """Cross-owner 404 coverage for all four file-scoped export routes,
    not just /codebook -- each calls the same file_repo.get_owned_file
    ownership check, but each is its own route wiring that could
    regress independently (e.g. a route that forgot Depends(require_user_id)
    or passed the wrong user_id through).
    """
    owner = await _make_user(session_factory, f"owner-{export_path}@example.com")
    other = await _make_user(session_factory, f"other-{export_path}@example.com")
    file_rec = await _make_file(session_factory, owner.id, f"{export_path}.csv", file_type)

    resp = client.get(
        f"/api/export/{file_rec.id}/{export_path}",
        cookies={"access_token": make_token(sub=str(other.id))},
    )
    assert resp.status_code == 404


async def test_export_bundle_unowned_project_rejected(client, session_factory, make_token):
    from backend.app.database import Project

    owner = await _make_user(session_factory, "bundle-owner@example.com")
    other = await _make_user(session_factory, "bundle-other@example.com")
    async with session_factory() as session:
        project = Project(user_id=owner.id, projectname="Owner's Project")
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id

    resp = client.get(
        f"/api/export/projects/{project_id}/bundle",
        cookies={"access_token": make_token(sub=str(other.id))},
    )
    assert resp.status_code == 403


async def test_export_memos_rejects_a_file_type_with_no_memos(client, session_factory, make_token):
    user = await _make_user(session_factory, "memo-type-guard@example.com")
    # summary files carry no row memos (see RowMemo's docstring: raw_data/
    # filtered_data/coding only) -- the route should reject, not silently
    # return an empty export.
    file_rec = await _make_file(session_factory, user.id, "s.csv", "summary")

    resp = client.get(
        f"/api/export/{file_rec.id}/memos",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 400


async def test_export_codebook_route_qdc_and_csv(client, session_factory, make_token):
    user = await _make_user(session_factory, "user_cb@example.com")
    file_rec = await _make_file(session_factory, user.id, "my_cb.csv", "codebook")
    code = {
        "code_uid": "u1",
        "name": "Theme Alpha",
        "position": 1,
        "family_uid": "",
        "family_name": "",
        "body": "",
    }
    async with session_factory() as session:
        await version_service.commit_codebook_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual", codes=[code]
        )
        await session.commit()

    # CSV
    resp_csv = client.get(
        f"/api/export/{file_rec.id}/codebook?format=csv",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert 'attachment; filename="my_cb_v1_codebook.csv"' in resp_csv.headers["content-disposition"]
    assert "Theme Alpha" in resp_csv.text

    # REFI-QDA -- the default, and what the dropdown leads with.
    resp_qdc = client.get(
        f"/api/export/{file_rec.id}/codebook?format=qdc",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_qdc.status_code == 200
    assert "application/xml" in resp_qdc.headers["content-type"]
    assert 'attachment; filename="my_cb_v1_codebook.qdc"' in resp_qdc.headers["content-disposition"]
    assert 'xmlns="urn:QDA-XML:codebook:1.0"' in resp_qdc.text
    assert 'name="Theme Alpha"' in resp_qdc.text

    resp_default = client.get(
        f"/api/export/{file_rec.id}/codebook",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_default.status_code == 200
    assert resp_default.text == resp_qdc.text

    # Formats this artifact no longer offers are rejected, not silently
    # served as the default.
    for bad in ("json", "md"):
        resp_bad = client.get(
            f"/api/export/{file_rec.id}/codebook?format={bad}",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp_bad.status_code == 422


async def test_export_coding_route_csv_and_json(client, session_factory, make_token):
    user = await _make_user(session_factory, "user_coding@example.com")
    file_rec = await _make_file(session_factory, user.id, "my_coding.csv", "coding")
    async with session_factory() as session:
        await version_service.commit_coding_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual"
        )
        entry = CodingEntry(
            file_id=file_rec.id,
            row_type="submission",
            post_id="p1",
            code="Code1",
            code_uid="u1",
            quote="Quoted evidence",
            start_offset=0,
            end_offset=15,
            notes="",
            coder="human",
            valid_from=1,
            valid_to=None,
        )
        session.add(entry)
        await session.commit()

    resp = client.get(
        f"/api/export/{file_rec.id}/coding?format=csv",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 200
    assert "Quoted evidence" in resp.text
    assert 'attachment; filename="my_coding_v1_segments_long.csv"' in resp.headers["content-disposition"]

    resp_j = client.get(
        f"/api/export/{file_rec.id}/coding?format=json",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_j.status_code == 200
    assert resp_j.json()["entries"][0]["quote"] == "Quoted evidence"

    # The frontend addresses artifacts by schemaname, not numeric id.
    resp_ref = client.get(
        f"/api/export/{file_rec.schemaname}/coding?format=csv",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_ref.status_code == 200
    assert "Quoted evidence" in resp_ref.text


async def test_export_memos_and_summary_routes(client, session_factory, make_token):
    user = await _make_user(session_factory, "user_memo@example.com")
    file_rec = await _make_file(session_factory, user.id, "my_data.csv", "coding")
    async with session_factory() as session:
        await version_service.commit_coding_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual"
        )
        memo = RowMemo(
            file_id=file_rec.id,
            row_type="submission",
            row_id="p1",
            body="Noteworthy post memo",
            author_user_id=user.id,
        )
        entry = CodingEntry(
            file_id=file_rec.id,
            row_type="submission",
            post_id="p1",
            code="Code1",
            code_uid="u1",
            quote="quote",
            start_offset=0,
            end_offset=5,
            valid_from=1,
            valid_to=None,
        )
        session.add_all([memo, entry])
        await session.commit()

    # Memos
    resp_m = client.get(
        f"/api/export/{file_rec.id}/memos?format=csv",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_m.status_code == 200
    assert "Noteworthy post memo" in resp_m.text

    # Memos default to markdown when no format is given.
    resp_m_default = client.get(
        f"/api/export/{file_rec.id}/memos",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_m_default.status_code == 200
    assert "text/markdown" in resp_m_default.headers["content-type"]
    assert "Noteworthy post memo" in resp_m_default.text

    # Summary -- markdown is the only format it offers.
    resp_s = client.get(
        f"/api/export/{file_rec.id}/summary?format=md",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_s.status_code == 200
    assert "text/markdown" in resp_s.headers["content-type"]
    assert "| Code1 |" in resp_s.text
    assert "| u1 |" in resp_s.text

    for bad in ("csv", "json"):
        resp_bad = client.get(
            f"/api/export/{file_rec.id}/summary?format={bad}",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp_bad.status_code == 422

    # Summary with version_no
    resp_sv = client.get(
        f"/api/export/{file_rec.id}/summary?version_no=1",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_sv.status_code == 200
    assert "(v1)" in resp_sv.text
    assert 'attachment; filename="my_data_v1_summary.md"' in resp_sv.headers["content-disposition"]


async def test_export_codebook_unknown_version_no_returns_404(client, session_factory, make_token):
    user = await _make_user(session_factory, "user_404cb@example.com")
    file_rec = await _make_file(session_factory, user.id, "cb.csv", "codebook")
    async with session_factory() as session:
        await version_service.commit_codebook_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual", codes=[]
        )

    resp = client.get(
        f"/api/export/{file_rec.id}/codebook?format=csv&version_no=99",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 404


async def test_export_coding_wide_layout_and_privacy_flags(client, session_factory, make_token):
    from backend.app.storage_models import Submission

    user = await _make_user(session_factory, "user_wide@example.com")
    file_rec = await _make_file(session_factory, user.id, "coding.csv", "coding")
    async with session_factory() as session:
        await version_service.commit_coding_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual"
        )
        session.add(Submission(file_id=file_rec.id, id="p1", title="t", selftext="body", author="bob", word_count=1))
        session.add(
            CodingEntry(
                file_id=file_rec.id, row_type="submission", post_id="p1", code="A", code_uid="a",
                quote="q", start_offset=0, end_offset=1, valid_from=1, valid_to=None,
            )
        )
        await session.commit()

    resp = client.get(
        f"/api/export/{file_rec.id}/coding?format=csv&layout=wide",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 200
    assert resp.text.strip().split("\r\n")[0] == "row_type,post_id,is_coded,total_codes"
    assert "bob" not in resp.text

    resp_opt_in = client.get(
        f"/api/export/{file_rec.id}/coding?format=csv&include_author=true&include_source_text=true",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_opt_in.status_code == 200
    assert "bob" in resp_opt_in.text
    assert "body" in resp_opt_in.text


async def test_export_project_bundle_route(client, session_factory, make_token):
    from backend.app.database import Project, async_link_file_to_project

    user = await _make_user(session_factory, "user_bundle@example.com")
    async with session_factory() as session:
        project = Project(user_id=user.id, projectname="Bundle Project")
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id

    file_rec = await _make_file(session_factory, user.id, "cb.csv", "codebook")
    async with session_factory() as session:
        await version_service.commit_codebook_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual", codes=[]
        )
        await async_link_file_to_project(session, file_rec.id, project_id)
        await session.commit()

    resp = client.get(
        f"/api/export/projects/{project_id}/bundle",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "bundle_project_project_bundle.zip" in resp.headers["content-disposition"]


async def test_export_project_bundle_requires_auth(client) -> None:
    resp = client.get("/api/export/projects/1/bundle")
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "file_type,suffix",
    [("summary", "summary"), ("codebook_comparison", "comparison"), ("coding_comparison", "comparison")],
)
async def test_export_document_returns_the_stored_markdown(
    client, session_factory, make_token, file_type, suffix
):
    user = await _make_user(session_factory, f"doc-{file_type}@example.com")
    file_rec = await _make_file(session_factory, user.id, f"my_{file_type}", file_type)
    async with session_factory() as session:
        await version_service.commit_blob_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="generated",
            content="# Findings\n\nThemes emerged.",
        )
        await session.commit()

    resp = client.get(
        f"/api/export/{file_rec.schemaname}/document",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 200
    assert resp.text == "# Findings\n\nThemes emerged."
    assert f'filename="my_{file_type}_v1_{suffix}.md"' in resp.headers["content-disposition"]


async def test_export_document_rejects_a_non_document_file(client, session_factory, make_token):
    user = await _make_user(session_factory, "doc-reject@example.com")
    file_rec = await _make_file(session_factory, user.id, "a_coding", "coding")
    resp = client.get(
        f"/api/export/{file_rec.id}/document",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 400
