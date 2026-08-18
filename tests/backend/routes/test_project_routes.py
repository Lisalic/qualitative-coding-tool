"""Tests for backend/app/api/project_routes.py.

`my_projects`, `create_project`, `update_project`, `rename_project` use
`Depends(get_db)` (sync SQLite via `override_db`). `list_projects` uses
`AsyncDatabaseManager()` directly, bypassing dependency injection, so it
is exercised separately against `override_async_db`.
"""

import pytest


def _auth_headers(make_token, sub="1"):
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


@pytest.mark.usefixtures("override_db")
class TestCreateProject:
    def test_create_requires_auth(self, client) -> None:
        resp = client.post("/api/create-project/", data={"name": "P1"})
        assert resp.status_code == 401

    def test_create_success(self, client, make_token) -> None:
        resp = client.post(
            "/api/create-project/",
            headers=_auth_headers(make_token),
            data={"name": "P1", "description": "desc"},
        )
        assert resp.status_code == 200
        body = resp.json()["project"]
        assert body["projectname"] == "P1"
        assert body["description"] == "desc"

    def test_create_strips_name_whitespace(self, client, make_token) -> None:
        resp = client.post(
            "/api/create-project/", headers=_auth_headers(make_token), data={"name": "  P1  "}
        )
        assert resp.json()["project"]["projectname"] == "P1"

    def test_create_whitespace_only_name_returns_400(self, client, make_token) -> None:
        # An empty string form value isn't sent by the test client at all
        # (indistinguishable from a missing field -> 422, covered below),
        # so this exercises the `if not name.strip()` branch specifically.
        resp = client.post(
            "/api/create-project/", headers=_auth_headers(make_token), data={"name": "   "}
        )
        assert resp.status_code == 400

    def test_create_missing_name_returns_422(self, client, make_token) -> None:
        resp = client.post("/api/create-project/", headers=_auth_headers(make_token), data={})
        assert resp.status_code == 422


@pytest.mark.usefixtures("override_db")
class TestUpdateProject:
    def _create(self, client, make_token, sub="1", name="Orig"):
        resp = client.post(
            "/api/create-project/", headers=_auth_headers(make_token, sub), data={"name": name}
        )
        return resp.json()["project"]["id"]

    def test_update_requires_auth(self, client) -> None:
        resp = client.post("/api/update-project/", data={"project_id": 1, "name": "x"})
        assert resp.status_code == 401

    def test_update_success(self, client, make_token) -> None:
        pid = self._create(client, make_token)
        resp = client.post(
            "/api/update-project/",
            headers=_auth_headers(make_token),
            data={"project_id": pid, "name": "New Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["project"]["projectname"] == "New Name"

    def test_update_missing_project_returns_404(self, client, make_token) -> None:
        resp = client.post(
            "/api/update-project/",
            headers=_auth_headers(make_token),
            data={"project_id": 999999, "name": "x"},
        )
        assert resp.status_code == 404

    def test_update_someone_elses_project_returns_403(self, client, make_token) -> None:
        pid = self._create(client, make_token, sub="1")
        resp = client.post(
            "/api/update-project/",
            headers=_auth_headers(make_token, sub="2"),
            data={"project_id": pid, "name": "hijacked"},
        )
        assert resp.status_code == 403

    def test_update_blank_name_returns_400(self, client, make_token) -> None:
        pid = self._create(client, make_token)
        resp = client.post(
            "/api/update-project/",
            headers=_auth_headers(make_token),
            data={"project_id": pid, "name": "   "},
        )
        assert resp.status_code == 400


@pytest.mark.usefixtures("override_db")
class TestMyFiles:
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/my-files/").status_code == 401

    def test_empty_for_new_user(self, client, make_token) -> None:
        resp = client.get("/api/my-files/", headers=_auth_headers(make_token))
        assert resp.status_code == 200
        assert resp.json() == {"projects": []}

    def test_default_file_type_is_raw_data(self, client, make_token, db_session) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        f = File(user_id=user.id, filename="f1", schemaname="proj_a", file_type="raw_data")
        f2 = File(user_id=user.id, filename="f2", schemaname="proj_b", file_type="filtered_data")
        db_session.add_all([f, f2])
        db_session.commit()

        resp = client.get("/api/my-files/", headers=_auth_headers(make_token, sub=str(user.id)))
        names = [p["display_name"] for p in resp.json()["projects"]]
        assert names == ["f1"]

    def test_codebook_file_type_includes_comparisons(self, client, make_token, db_session) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        f1 = File(user_id=user.id, filename="cb", schemaname="proj_a", file_type="codebook")
        f2 = File(
            user_id=user.id, filename="cmp", schemaname="cmp_a", file_type="codebook_comparison"
        )
        db_session.add_all([f1, f2])
        db_session.commit()

        resp = client.get(
            "/api/my-files/?file_type=codebook",
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        names = {p["display_name"] for p in resp.json()["projects"]}
        assert names == {"cb", "cmp"}


@pytest.mark.usefixtures("override_db")
class TestRenameFile:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/rename-file/", data={"schema_name": "proj_a", "display_name": "x"}
        )
        assert resp.status_code == 401

    def test_rename_success(self, client, make_token, db_session) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        f = File(user_id=user.id, filename="old", schemaname="proj_a", file_type="raw_data")
        db_session.add(f)
        db_session.commit()

        resp = client.post(
            "/api/rename-file/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={"schema_name": "proj_a", "display_name": "new-name"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "new-name"

    def test_rename_missing_file_returns_404(self, client, make_token) -> None:
        resp = client.post(
            "/api/rename-file/",
            headers=_auth_headers(make_token),
            data={"schema_name": "proj_missing", "display_name": "x"},
        )
        assert resp.status_code == 404

    def test_rename_someone_elses_file_returns_404(self, client, make_token, db_session) -> None:
        # Ownership is enforced via the WHERE clause itself (File.user_id
        # == user_id), so a mismatch surfaces as 404, not 403.
        from backend.app.database import File, User

        owner = User(email="owner@x.com", password="hash")
        db_session.add(owner)
        db_session.commit()
        f = File(user_id=owner.id, filename="old", schemaname="proj_a", file_type="raw_data")
        db_session.add(f)
        db_session.commit()

        resp = client.post(
            "/api/rename-file/",
            headers=_auth_headers(make_token, sub="999999"),
            data={"schema_name": "proj_a", "display_name": "x"},
        )
        assert resp.status_code == 404


class TestListProjects:
    """`list_projects` constructs `AsyncDatabaseManager()` directly rather
    than using `Depends(get_async_db)`, so it needs
    `patch_async_database_manager` rather than `override_async_db`.
    """

    def test_requires_auth(self, client) -> None:
        assert client.get("/api/projects/").status_code == 401

    def test_empty_for_new_user(self, client, make_token, patch_async_database_manager) -> None:
        resp = client.get("/api/projects/", headers=_auth_headers(make_token))
        assert resp.status_code == 200
        assert resp.json() == {"projects": []}

    async def test_lists_own_projects_with_files(
        self, client, make_token, patch_async_database_manager
    ) -> None:
        # NOTE: `async_link_file_to_project` builds its INSERT via
        # `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing`,
        # which only compiles against the postgresql dialect -- it cannot
        # run against this SQLite fixture. Insert into the plain
        # `project_files` association table directly instead; the
        # Postgres-specific ON CONFLICT path is covered by the opt-in
        # integration suite (tests/backend/integration/).
        SessionLocal = patch_async_database_manager
        from backend.app.database import File, Project, User, project_files_table

        async with SessionLocal() as session:
            user = User(email="a@b.com", password="hash")
            session.add(user)
            await session.commit()

            proj = Project(user_id=user.id, projectname="P1")
            session.add(proj)
            await session.commit()

            f = File(user_id=user.id, filename="f1", schemaname="proj_a", file_type="raw_data")
            session.add(f)
            await session.commit()

            await session.execute(
                project_files_table.insert().values(project_id=proj.id, file_id=f.id)
            )
            await session.commit()
            uid = user.id

        resp = client.get("/api/projects/", headers=_auth_headers(make_token, sub=str(uid)))
        assert resp.status_code == 200
        projects = resp.json()["projects"]
        assert len(projects) == 1
        assert projects[0]["projectname"] == "P1"
        assert projects[0]["files"][0]["display_name"] == "f1"
