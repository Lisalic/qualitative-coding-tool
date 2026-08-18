# Core Concepts

## The artifact model

Everything the pipeline produces is a `File` row (`backend/app/database.py`) with:

- a `file_type`: `raw_data`, `filtered_data`, `codebook`, `coding`, `codebook_comparison`, `coding_comparison`, or `summary` (also `comparison`, a generic fallback used by `POST /api/save-comparison/` when no more specific type is passed)
- a `schemaname` — see below
- optional `description`, `systemprompt`, `userprompt` (the prompts used to generate it, when applicable)

Each pipeline stage (import → filter → generate codebook → apply codebook → compare → summarize) reads from one or more parent artifacts and **writes a new artifact** rather than mutating the source. Parent/child relationships are recorded in `file_dependencies` (`backend/app/database.py`), so the UI can trace an analysis chain back to its raw data. See the dependency graph in [workflow.md#end-to-end-workflow](workflow.md#end-to-end-workflow).

## `schemaname`: an opaque identifier, not a Postgres schema

Historically each artifact got its own dynamic Postgres schema (`proj_<hex>` for raw/filtered/codebook/coding data, `cmp_<hex>` for comparisons, `sum_<hex>` for summaries), and `files.schemaname` held that schema's real name.

That has changed. Content now lives in a small set of **fixed, indexed tables** (`submissions`, `comments`, `artifact_content`, `coding_entries` — see [architecture.md#storage](architecture.md#storage)), all keyed by `file_id`. `files.schemaname` is kept as-is purely as an **opaque identifier string** — the frontend still passes it around (e.g. `database=proj_a1b2c3` in a form submission) — but every backend repository resolves it to `files.id` via `backend/app/repositories/file_repo.py::resolve_file_id` before querying, rather than splicing it into a dynamic schema name. The old per-artifact Postgres schemas still physically exist in the database as a read-only rollback fallback; dropping them is a separate, deliberate, explicitly-confirmed step (`backend/scripts/drop_migrated_schemas.py`), not something to assume has happened.

Practical consequence for the tool pages in this documentation: whenever a form field is labeled "Database" or a codebook/coding selector shows a `proj_<hex>` value, that value is this opaque identifier, validated client-side against `/^proj_[A-Za-z0-9_]+$/` (`frontend/src/lib/apiContracts.js`) and server-side against the same pattern (`backend/app/api/schemas.py`).

## Projects

A `Project` groups `File` rows via the `project_files` many-to-many table. Projects are optional at creation time for most artifacts (`project_id` is nullable on every AI-tool form) but are the primary way the UI scopes "which files belong together" on the Project detail page and in source-selection dropdowns.

## API key handling

Every AI-backed tool (Filter Data, Generate Codebook, Apply Codebook, Compare Codebooks, Compare Codings, Summarize Coding) needs an OpenRouter API key to call the LLM. The key is:

- entered once in the navbar (`frontend/src/components/layout/Navbar.jsx`, `useApiKey.js`), stored in `localStorage.apiKey`
- **never** a field on any tool's own form
- read at submit time by each tool panel; if absent, submission is blocked client-side with an error like `"Error: API key not set. Please set your API key in the navbar."`
- sent to the backend as `api_key` in the form body, then passed through to `enqueue_job` as `runtime_extra` — meaning it is **held only in the job runner's in-memory closure for that process's lifetime**, never written to the `jobs` table or any other persisted row. See [architecture.md#background-jobs](architecture.md#background-jobs) for the durability trade-off this implies.

## Sampling

Most AI tools operate on a random sample of the source data rather than all of it, controlled by a `sample_percentage` field (a 1–100 slider in the UI, except Generate Codebook which allows 0–100). Sampling is done in Postgres via `ORDER BY RANDOM() LIMIT :n` (`backend/app/repositories/raw_data_repo.py`), not client-side.

## Model catalog

The list of selectable AI models comes from `GET /api/models`, backed by an in-memory catalog (`backend/app/ai_models.py`) refreshed once a day from OpenRouter's public model list. See [architecture.md#model-catalog](architecture.md#model-catalog) for the free/paid split and a caveat about which module-level model defaults do and don't follow the daily refresh.
