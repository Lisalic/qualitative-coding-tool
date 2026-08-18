# Projects

## Purpose

Organize files into named groups, and manage (view, rename, delete, merge) files within a project.

## Where to find it

- `/` (Home, via `AuthGate` when authenticated) → `pages/Home.jsx` — list projects, create a new one.
- `/project/:projectId` → `pages/Project.jsx` — a single project's file manager, tabbed by artifact type.

## Prerequisites

None to create a project. Files must already exist (via [Import Data](import-data.md) or a pipeline tool) to appear in a project's tabs.

## Inputs

**Create project** (Home page):

| Field | Required | Notes |
|---|---|---|
| Project Name | yes | client-checked non-blank |
| Description | no | |

**Edit project header** (Project detail page):

| Field | Required | Notes |
|---|---|---|
| Name | yes | |
| Description | no | |

**Rename file** (inline row edit, any tab):

| Field | Required | Notes |
|---|---|---|
| Display Name | yes | non-blank |
| Description | no | |

**Merge databases** (database/filtered tabs only): select ≥2 files via checkboxes, plus a required merged name.

## What happens on submit

All project/file admin actions are direct (non-job) calls:

- Create: `POST /api/create-project/` (`name`, `description`) — sync FormData.
- Update header: `POST /api/update-project/` (`project_id`, `name`, `description`).
- Rename file: `POST /api/rename-file/` (`schema_name`, `display_name`, `description`).
- Delete file: confirm dialog (`ToastService.confirm`) → `DELETE /api/delete-database/{schema_name}`.
- Merge: confirm dialog → `POST /api/merge-databases/` (`databases` as a JSON array, `name`, `project_id`) — creates a new `raw_data` file combining rows from all selected sources, deduplicated by row id, with a `FileDependency` back to every owned source.

The Project page has no single-project-by-id endpoint — `useProjectPage.js` fetches `GET /api/projects/` and finds the matching project client-side.

Files are organized into tabs: `database` (`raw_data`), `filtered` (`filtered_data`), `codebook` (`codebook` + `codebook_comparison`, with a sub-filter), `coding` (`coding` + `coding_comparison`, with a sub-filter), `summary`.

## Output

- Create/update: the `Project` row.
- Rename: updates `filename`/`description` on the target `File` row.
- Delete: removes the `File` row and its content rows (`FileDependency`, `FileTable`, `submissions`/`comments`/`artifact_content`/`coding_entries` for that `file_id`) — but does **not** drop any leftover legacy Postgres schema for that file (deliberate, see [architecture.md#storage](../architecture.md#storage)).
- Merge: a new `raw_data` File artifact, linked to its source files via `FileDependency` and to the chosen project.

"Add X" buttons in `ProjectFilesSection` navigate to the corresponding tool page. `/filter`, `/codebook-generate`, and `/codebook-apply` carry `state.projectId`, which those panels read via `useInitialProjectId` to pre-select the project on arrival. `/import` has no project selector to preselect (project is chosen as a required form field instead), and `/summarize-coding` has no project-scoped picker at all, so neither button passes `state.projectId`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Name is required" | Blank project or file name on submit |
| Merge does nothing / "No rows found" | All selected sources merged to zero rows; the merge is rolled back and no file is created (`file_migrated: false`) |
| Merge fails with a not-found error | A selected source schema doesn't resolve to a `raw_data` file owned by the caller — `merge-databases` resolves and ownership-checks every source via `file_repo.get_owned_file` before reading it |

## Developer reference

- Frontend: `pages/Home.jsx` + `components/project/useHomePage.js`, `components/project/ProjectsListSection.jsx`, `components/project/CreateProjectSection.jsx`, `components/project/ProjectCard.jsx`; `pages/Project.jsx` + `components/project/useProjectPage.js`, `ProjectHeaderSection.jsx`, `ProjectFilesSection.jsx`, `FileRowActions.jsx`.
- Backend: `backend/app/api/project_routes.py` → `backend/app/services/project_service.py` → `backend/app/repositories/project_repo.py` / `file_repo.py`. Merge/delete/rename of files themselves live in `backend/app/api/file_routes.py` → `backend/app/services/file_service.py`.
- Endpoints: `GET /api/projects/`, `POST /api/create-project/`, `POST /api/update-project/`, `GET /api/my-files/`, `POST /api/rename-file/`, `POST /api/merge-databases/`, `DELETE /api/delete-database/{schema}` — see [api-reference.md](../api-reference.md#projects--backendappapiproject_routespy).
