# Apply Codebook

## Purpose

Start a `coding` artifact against a chosen codebook, then code it in an
iterative 3-pane workspace — the same workspace [View Coding](view-coding.md)
opens on an existing artifact.

## Where to find it

Sidebar → Apply Codebook, the project page's **Add Coding** button, or
`/codebook-apply` → `pages/ApplyCodebook.jsx` →
`components/coding-editor/CodingEditor.jsx`.

## Two steps on one route

**Setup** (`components/coding-editor/CodingSetupPanel.jsx`) chooses the
source database, the codebook, the content scope, and how much to sample,
then creates the artifact — always **uncoded**: rows copied in, codebook
snapshotted, zero `coding_entries`. There is no "code everything now"
option; a one-shot classifier pass that coded the whole artifact up front
(`POST /api/apply-codebook/`) was retired once the workspace's AI recode
covered the same ground with a review step in front of it.

**Workspace** — on success, the same screen swaps in the View Coding
3-pane reader on the artifact just created (`CodingWorkspaceSection.jsx`):
a document list on the left, the active document's full text and applied
codes in the center, and the codebook on the right. See
[View Coding](view-coding.md) for the workspace itself — reading,
tagging, keyboard shortcuts (`1`-`9` to apply a code, `j`/`k` to move
between documents), AI recode, and Save Changes all work identically
whether the artifact came from here or from the picker there.

## Prerequisites

At least one dataset and one codebook. The setup step blocks entirely if
no codebooks exist for the user. No API key is needed to create the
artifact — only the workspace's AI recode needs one.

## Setup inputs

| Field | Required | Default | Constraints | Notes |
|---|---|---|---|---|
| Database Type | — | `unfiltered` | `unfiltered` \| `filtered` | |
| Select Database | yes | — | must resolve to `proj_<id>` | |
| Select Project | yes | — | must be a project the caller owns | pre-selected via `state.projectId` when arriving from a project page's "Add" button; every artifact belongs to a project |
| Select Codebook | yes | first available | numeric File id **or** `proj_<hex>` schema | auto-defaults to the first codebook in the list |
| Content to Sample | — | `both` | Posts + Comments \| Posts Only \| Comments Only | auto-narrows to whichever type actually has rows |
| Report Name | yes | — | non-blank | |
| Description | no | — | | |

## What happens on submit

`requestJson` → `POST /api/coding/manual` →
`coding_service.create_manual_coding`, synchronous (no LLM call). Copies
every row in the chosen content scope (the request still carries
`sample_percentage`, always `100` from this panel — there is no sampling
control) and their memos in,
snapshots the applied codebook's codes, records `derived_from` edges back
to both the source data and the codebook, and commits v1 with
`origin="edited"` and no `model`/`system_prompt`/`prompt_meta` — `_materialize_coding_artifact`
is the coding editor's only path to creating an artifact.

## Output

`{message, file: {id, schema_name, filename}, counts}`. The panel hands
the new artifact straight to the workspace rather than showing a success
banner — coding is iterative, so a finished setup step is a starting
point, not a result.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Submit disabled, "No codebooks available" | No codebook artifacts exist yet for this user — go create one via [Codebook](codebook.md) |
| `MissingFieldsError` mentioning "codebook (must be numeric File id or proj_<id> schema)" | The codebook reference is neither a valid `proj_<hex>` string nor parseable as an integer |
| "No records were sampled from the selected database" | Sample size or content scope excluded every row — widen either |

## Developer reference

- Frontend: `pages/ApplyCodebook.jsx`, `components/coding-editor/`
  (`CodingEditor.jsx`, `CodingSetupPanel.jsx`),
  `lib/apiContracts.js::buildManualCodingPayload`. Workspace files are the
  same ones [View Coding](view-coding.md) documents.
- Backend: `backend/app/api/coding_routes.py::POST /coding/manual` →
  `backend/app/services/coding_service.py::create_manual_coding` →
  `_read_codebook_as_parent`, `_sample_rows_for_coding`,
  `_materialize_coding_artifact` → `backend/app/repositories/raw_data_repo.py`,
  `memo_repo.py`, `coding_repo.py::bulk_insert_coding_entries` (a no-op
  here, since nothing is coded yet).
- Storage written: new `files` row (`coding`), two `artifact_edges` rows
  (source data + codebook), `codebook_codes` snapshot rows, `submissions`/
  `comments` rows copied under the new `file_id`, zero `coding_entries`.
- Endpoint: `POST /api/coding/manual` — see
  [api-reference.md](../api-reference.md#coding--backendappapicoding_routespy).
