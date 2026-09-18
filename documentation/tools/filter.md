# Filter

## Purpose

Produce a `filtered_data` artifact — a subset of a raw or filtered dataset,
chosen by hand and/or with AI assistance — without mutating the source.

## Where to find it

Sidebar → Filter Data, the data viewer's **Filter** button, or `/filter` →
`pages/Filter.jsx` → `components/filter-editor/FilterEditor.jsx`.

## Layout

A 3-pane workspace, matching the coding editor's shape:

- **Left — row list.** Every submission/comment on the current page, each
  with a decision mark (kept/skipped/undecided) and quick Keep/Skip
  buttons. A status filter (All/Undecided/Kept/Skipped) narrows what's
  shown, scoped to the loaded page — there is no server-side equivalent
  to the coding workspace's coded/uncoded row filter here.
- **Center — reader pane.** The selected row's full text, Keep/Skip for
  it, and its memo editor (`MemoEditor`, shared with the raw/filtered data
  viewers).
- **Right — AI assist + create form.** The AI filter (collapsed by
  default) plus the fields — name, description, project — that will name
  the artifact.

## Prerequisites

At least one raw or filtered dataset to filter from. An OpenRouter API key
set in the navbar (see [concepts.md#api-key-handling](../concepts.md#api-key-handling))
is only needed to run the AI assist — marking rows by hand and submitting
needs no key at all.

## Working the rows

Click a row in the left pane to open it in the reader; Keep/Skip either
there or from the list. The AI filter (prompt, keywords, model, minimum
words, sample size) proposes rows from the **undecided pool only** — rows
already ruled on are never re-litigated — and accepted suggestions are
badged `(added by AI)`. Selections persist to `localStorage` per source
database (`useFilterEditorState`/`lib/filterEditorState.js`), so a refresh
or a multi-minute AI run doesn't lose the work.

## What happens on submit

Two independent requests, neither of which is a one-shot "do everything":

- **AI assist** (optional, repeatable): `postJsonAndPoll` → `POST
  /api/filter-preview/` (job type `filter_preview`) → `202 {job_id,
  status}` → poll. Runs `data_service._run_ai_filter` and returns the row
  ids it would keep — it creates nothing.
- **Create** (once, when ready): `requestJson` → `POST
  /api/filtered-data/manual` → `data_service.create_manual_filtered_data`,
  synchronous (no LLM call). Copies exactly the kept rows (and their
  memos) via `raw_data_repo.copy_rows_by_id`/`memo_repo.copy_memos_by_id`,
  records a `derived_from` edge back to the source, and commits v1 with
  `origin="edited"` and no `system_prompt`/`prompt_meta` — an AI assist
  during editing is not the same claim as "a model produced this."

## Output

Manual-create response: `{message, file: {id, schema_name, filename},
counts}`. Success banner links to [Data Browser](data-browser.md)
(`/filtered-data`) with the new file preselected.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "API key not set. Please set your API key in the navbar." (AI assist only) | No `localStorage.apiKey` |
| Create button stays disabled | No rows kept yet, or the name field is blank |
| AI assist proposes nothing new | Every undecided row was already sent and none matched — try a different prompt, or increase sample size |

## Developer reference

- Frontend: `pages/Filter.jsx`, `components/filter-editor/` (`FilterEditor.jsx`,
  `FilterRowList.jsx`, `FilterReaderPane.jsx`, `FilterDecisionsRail.jsx`,
  `FilterAiPanel.jsx` on the shared `components/forms/AiAssistPanel.jsx`),
  `lib/filterEditorState.js`, `lib/apiContracts.js::buildFilterPreviewPayload`/`buildManualFilterPayload`.
- Backend: `backend/app/api/data_routes.py` (`POST /filter-preview/`, `POST
  /filtered-data/manual`) → `backend/app/services/data_service.py`
  (`start_filter_preview_job`/`_run_filter_preview_job`,
  `create_manual_filtered_data`) → `backend/scripts/filter_db.py` (AI
  filtering), `backend/scripts/tag_expansion.py` (keyword expansion) →
  `backend/app/repositories/raw_data_repo.py`.
- Storage written (create only): new `files` row (`filtered_data`), an
  `artifact_edges` row back to the source, `file_tables`,
  `submissions`/`comments` rows copied under the new `file_id`.
- Endpoints: `POST /api/filter-preview/`, `POST /api/filtered-data/manual`
  — see [api-reference.md](../api-reference.md#data--backendappapidata_routespy).
