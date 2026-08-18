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
| [Filter Data](tools/filter-data.md) | `/filter` | pipeline (AI) |
| [Generate Codebook](tools/generate-codebook.md) | `/codebook-generate` | pipeline (AI) |
| [View Codebook](tools/view-codebook.md) | `/codebook-view` | viewer/editor |
| [Apply Codebook](tools/apply-codebook.md) | `/codebook-apply` | pipeline (AI) |
| [View Coding](tools/view-coding.md) | `/coding-view` | viewer/editor |
| [Compare Codebooks](tools/compare-codebooks.md) | `/compare-codebook` | pipeline (AI) |
| [Compare Codings](tools/compare-codings.md) | `/compare-coding` | pipeline (AI) |
| [Summarize Coding](tools/summarize-coding.md) | `/summarize-coding` | pipeline (AI) |
| [View Summary](tools/view-summary.md) | `/summaryview` | viewer |
| [Prompt Manager](tools/prompt-manager.md) | modal (no route) | admin |

## Conventions used in these docs

- File paths are relative to the repo root and are clickable links to the actual source.
- "AI tool" means the six endpoints backed by the background job system (`filter_data`, `generate_codebook`, `apply_codebook`, `compare_codebooks`, `compare_codings`, `summarize_coding`) — see [architecture.md#background-jobs](architecture.md#background-jobs).
- Every AI tool requires an OpenRouter API key set in the navbar (stored in `localStorage.apiKey`), never entered on the tool's own form — see [concepts.md#api-key-handling](concepts.md#api-key-handling).
- Field tables in tool pages record the *actual* validation constraints (e.g. required-ness, min/max, regex), sourced from `frontend/src/lib/apiContracts.js` and `backend/app/api/schemas.py`, not just field names.
