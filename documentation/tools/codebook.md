# Create Codebook

## Purpose

Write a `codebook` artifact by hand, with the source data in view — either
a fresh codebook, or another data-anchored pass over an existing one.

## Where to find it

Sidebar → Create Codebook, the project page's **Add Codebook** button, or
`/codebook` → `pages/Codebook.jsx` → `components/codebook-editor/CodebookEditor.jsx`.

## Layout

A 3-pane workspace, matching the filter and coding editors' shape:

- **Left — source reader.** The corpus, one card per post/comment
  (`CodebookSourceReader.jsx`). Read-only: nothing here is decided per
  row, unlike the filter editor.
- **Center — reader pane.** The selected row's full text and its memo
  editor.
- **Right — codebook rail.** The draft codebook (`CodeLegend`, always in
  edit mode here), a review tray for AI-proposed codes, and the AI assist
  tool — plus, in New mode, the fields (name, description, project) that
  will name the artifact.

## Modes

Chosen from the top toolbar:

- **New** — create a fresh codebook (`POST /api/codebook/manual`).
- **Refine** — open an existing codebook and do another pass over it,
  saving through `PUT /api/codebook/{ref}`, the same endpoint the
  [View Codebook](view-codebook.md) editor uses. A refinement is an
  ordinary new version, not a special kind of write, and identity
  (`code_uid`/`family_uid`) carries through so a rename reads as a rename
  in the version diff rather than a delete-plus-add. Refine asks only for
  the codebook: the source database is read off that codebook's own
  lineage (`GET /api/artifacts/{ref}/lineage`, first `raw_data`/
  `filtered_data` parent) and shown read-only, with a **Use another
  database** button that falls back to the picker when the second pass
  should run against different data.

## Prerequisites

At least one raw or filtered dataset to read from. An OpenRouter API key
set in the navbar is only needed to run the AI assist.

## Working the draft

Add code families and codes directly in the right rail (`CodeLegend`'s
edit mode) while reading the corpus on the left. The AI assist tool
(collapsed by default) proposes codes into the **review tray** — one card
per code, showing every field the model produced — and each is accepted
or dismissed individually; nothing enters the codebook without an
explicit accept. The current draft is sent as `existing_codes` with every
run, so repeated runs propose only what's still missing, and dismissals
are remembered so a later run can't re-offer the same code. The draft
persists to `localStorage` per (source, target) pair
(`useCodebookEditorState`/`lib/codebookEditorState.js`).

## What happens on submit

- **AI assist** (optional, repeatable): `postJsonAndPoll` → `POST
  /api/codebook-preview/` (job type `codebook_preview`) → `202 {job_id,
  status}` → poll. Runs the generation pass but **creates nothing** — no
  `File`, no `ArtifactVersion`, no edge, no commit.
- **Create / Save** (once, when ready):
  - New: `requestJson` → `POST /api/codebook/manual` →
    `codebook_service.create_manual_codebook`, synchronous (no LLM call).
    Commits v1 with `origin="edited"` and no `model`/`system_prompt`/
    `prompt_meta`.
  - Refine: `requestJson` → `PUT /api/codebook/{ref}` with the flattened
    draft's codes — the same save path View Codebook uses.

## Output

Manual-create response: `{message, file: {id, schema_name, filename}}`.
Success banner links to [View Codebook](view-codebook.md) with the new
codebook preselected. A Refine save shows an inline "Saved as a new
version" message instead.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "API key not set. Please set your API key in the navbar." (AI assist only) | No `localStorage.apiKey` |
| Create/Save button stays disabled | No codes in the draft yet, the name field is blank (New), or no codebook is selected (Refine) |
| AI assist proposes a code already in the draft | Shouldn't happen — proposals already covered by `existing_codes` are dropped server-side (`codebook_service._code_dedupe_key`); if it does, the dedupe key and `lib/codebookEditorState.js::codeKey` have drifted out of step |

## Developer reference

- Frontend: `pages/Codebook.jsx`, `components/codebook-editor/`
  (`CodebookEditor.jsx`, `CodebookSourceReader.jsx`, `CodebookReaderPane.jsx`,
  `CodebookCodesRail.jsx`, `CodebookProposalTray.jsx`, `CodebookAiPanel.jsx`
  on the shared `components/forms/AiAssistPanel.jsx`),
  `lib/codebookEditorState.js`,
  `lib/apiContracts.js::buildCodebookPreviewPayload`/`buildManualCodebookPayload`.
- Backend: `backend/app/api/codebook_routes.py` (`POST /codebook-preview/`,
  `POST /codebook/manual`, `PUT /codebook/{ref}`) →
  `backend/app/services/codebook_service.py`
  (`start_codebook_preview_job`/`_run_codebook_preview_job`,
  `create_manual_codebook`, `save_project_codebook`) →
  `backend/scripts/codebook_generator.py` (map-reduce generation) →
  `backend/app/services/version_service.py::commit_codebook_version`.
- Storage written (create only): new `files` row (`codebook`), an
  `artifact_edges` row back to the source, `codebook_codes` rows on v1.
- Endpoints: `POST /api/codebook-preview/`, `POST /api/codebook/manual`,
  `PUT /api/codebook/{ref}` — see
  [api-reference.md](../api-reference.md#codebooks--backendappapicodebook_routespy).
