# View Codebook

## Purpose

Inspect and edit a codebook, either as raw markdown text or as a structured tree of code families/codes; jump into a comparison.

## Where to find it

Sidebar → View Codebook (Views group), or `/codebook-view` → `pages/ViewCodebook.jsx`.

## Prerequisites

At least one codebook artifact (from [Generate Codebook](generate-codebook.md), or a saved [Compare Codebooks](compare-codebooks.md) result). No API key needed — this tool is read/write against stored content, not an LLM call.

## Inputs

| Control | Notes |
|---|---|
| Project filter + codebook picker | `ArtifactSelector`; lists via `GET /api/list-codebooks` |
| View mode tabs | "Show Text" (markdown editor) or "Show Tree" (structured family/code view) |
| Edit form (text mode) | Name (required, non-blank) + a full content textarea |

## What happens on submit

All direct (non-job) calls:

- Load: `GET /api/codebook?codebook_id=...` (returns `codebook`, `systemprompt`, `userprompt`) for text mode; `GET /api/parse-codebook?codebook_id=...` for tree mode.
- Save (text mode): `POST /api/save-file-codebook/` (`schema_name`, `display_name`, `content`) — overwrites the artifact's content and display name in place.

Tree mode (`CodebookTree.jsx`) renders collapsible code families with Expand All/Collapse All; code bodies render as markdown. Text mode (`MarkdownView.jsx`) also shows the original system/user prompts when present, and has a Compare button.

## Output

Overwrites the existing codebook's content/name — does not create a new artifact. `onSelectionChangeAfterSave` refreshes the codebook list and name after a save.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Name cannot be empty" | Blank name on save |

## Developer reference

- Frontend: `pages/ViewCodebook.jsx`, `components/codebook/useViewCodebookPage.js`, `components/codebook/CodebookWorkspaceSection.jsx`, `ArtifactMarkdownSection.jsx`, `MarkdownView.jsx`, `CodebookTree.jsx`, `components/primitives/ArtifactSelector.jsx`, `ViewModeTabs.jsx`.
- Backend: `backend/app/api/codebook_routes.py` (`GET /codebook`, `GET /parse-codebook`, `GET /list-codebooks`, `POST /save-file-codebook/`) → `backend/app/services/codebook_service.py` → `backend/app/repositories/artifact_content_repo.py`. Tree parsing: `backend/scripts/display_codebook.py::parse_codebook_to_json`.
- Endpoints — see [api-reference.md](../api-reference.md#codebooks--backendappapicodebook_routespy).
