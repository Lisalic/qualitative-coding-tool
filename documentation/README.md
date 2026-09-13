# Documentation

Reference documentation for the Qualitative Coding Tool: what each tool does, how a user drives it, and how it's wired end to end (route → service → repository → script/storage).

## Start here

- [getting-started.md](getting-started.md) — prerequisites, environment variables, install, and running the app locally.
- [concepts.md](concepts.md) — the artifact model, `file_type`/`schemaname`, lineage, and how the OpenRouter API key flows through the app.
- [architecture.md](architecture.md) — frontend/backend layering, the background jobs system, the LLM call seam, storage tables, auth, and the model catalog.
- [api-reference.md](api-reference.md) — every backend endpoint, grouped by router, with request/response shapes.
- [workflow.md](workflow.md) — narrative feature-by-feature walkthrough of the full pipeline (import → filter → generate codebook → apply codebook → compare → summarize), with a workflow diagram.
- [style-guide.md](style-guide.md) — the frontend's visual identity (palette, typography, component patterns).
- [known-issues.md](known-issues.md) — verified, currently-unfixed defects, kept up to date as they're found and resolved.

## Tools

Each tool in the app has its own page under [tools/](tools/README.md) covering: purpose, where to find it, prerequisites, inputs, what happens on submit, output, troubleshooting, and a developer reference (file paths, endpoint, backend call chain).

| Tool | Route(s) | Kind |
|---|---|---|
| [Authentication](tools/authentication.md) | `/login`, `/register` | admin |
| [Projects](tools/projects.md) | `/`, `/project/:projectId` | admin |
| [Import Data](tools/import-data.md) | `/import` | pipeline |
| [Data Browser](tools/data-browser.md) | `/data`, `/filtered-data` | viewer |
| [Filter](tools/filter.md) | `/filter` | editor |
| [Create Codebook](tools/codebook.md) | `/codebook` | editor |
| [View Codebook](tools/view-codebook.md) | `/codebook-view` | viewer/editor |
| [Apply Codebook](tools/apply-codebook.md) | `/codebook-apply` | editor |
| [View Coding](tools/view-coding.md) | `/coding-view` | viewer/editor |
| [Compare Codebooks](tools/compare-codebooks.md) | `/compare-codebook` | viewer (computed) |
| [Integrate Codebook](tools/integrate-codebook.md) | `/integrate-codebook` | editor |
| [Compare Codings](tools/compare-codings.md) | `/compare-coding` | viewer (computed) |
| [Summarize Coding](tools/summarize-coding.md) | `/summarize-coding` | pipeline (AI) |
| [View Summary](tools/view-summary.md) | `/summaryview` | viewer |
| [Prompt Manager](tools/prompt-manager.md) | modal (no route) | admin |

## Conventions used in these docs

- File paths are relative to the repo root and are clickable links to the actual source.
- "editor" means a 3-pane human-in-the-loop workspace (Filter, Codebook, Apply Codebook, Integrate Codebook) where the researcher works by hand and an AI-assist panel only *proposes*, backed by the background job system (`filter_preview`, `codebook_preview`, `recode_items`, `integrate_codebook_preview`) — see [architecture.md#background-jobs](architecture.md#background-jobs). "pipeline (AI)" means a one-shot job with no review step (`summarize_coding`) — the equivalents for filter/codebook/coding were retired once their editors covered everything they did. "viewer (computed)" means a deterministic, no-LLM diff computed synchronously on request (`GET /api/comparison/codebooks`/`codings`) — the LLM-generated comparison job these two tools used to also offer has been retired.
- Every AI-backed tool requires an OpenRouter API key set in the navbar (stored in `localStorage.apiKey`), never entered on the tool's own form — see [concepts.md#api-key-handling](concepts.md#api-key-handling).
- Field tables in tool pages record the *actual* validation constraints (e.g. required-ness, min/max, regex), sourced from `frontend/src/lib/apiContracts.js` and `backend/app/api/schemas.py`, not just field names.
