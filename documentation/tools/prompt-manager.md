# Prompt Manager

## Purpose

Save, reuse, edit, and delete prompt text across sessions, scoped by which tool it's for.

## Where to find it

Not a route — a modal (`components/forms/PromptManager.jsx`) opened by the "Load prompt" button next to the prompt textarea on three of the six AI tools: [Filter Data](filter-data.md), [Generate Codebook](generate-codebook.md), and [Apply Codebook](apply-codebook.md) (`promptType` = `filter`/`generate`/`apply` respectively). [Compare Codebooks](compare-codebooks.md), [Compare Codings](compare-codings.md), and [Summarize Coding](summarize-coding.md) each have their own inline example-prompt button instead and do not integrate with this saved library.

## Prerequisites

None. No API key needed — this is plain CRUD, no LLM call.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Prompt name | auto-generated (`Prompt N`) when saving from a tool panel; editable inline in the manager | |
| Prompt content | yes | "Please enter prompt content" if blank |

## What happens on submit

All direct (non-job) calls via the axios `api` instance:

- Save from a tool panel: `frontend/src/lib/savePromptToLibrary.js` computes the next `Prompt N` name via `GET /api/prompts/?prompt_type=...`, then `POST /api/prompts/` (`promptname`, `prompt`, `type`, optional `user_id`). Dispatches a `promptSaved` window event, which the manager listens for to refresh its list.
- List: `GET /api/prompts/?prompt_type=...`.
- Edit: `POST /api/prompts/{id}/update`.
- Delete: `DELETE /api/prompts/{id}`.

The built-in example prompt for the active tool (`apiContracts.EXAMPLE_PROMPTS[promptType]`) is injected into the list as a pseudo-item (id `__example_prompt__`, labeled "Built-in", load-only — it can't be edited or deleted).

## Output

Rows in the `prompts` table, scoped to the user.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Please enter prompt content" | Blank prompt text on save |
| 404/403 editing or deleting a prompt | Prompt doesn't exist, or belongs to another user |
| Saved prompt doesn't appear for Compare/Summarize tools | Those three tools' prompt fields don't wire into this library at all — they use a plain textarea (`CompareModelPromptPanel`) instead of `PromptTextareaWithActions`, unlike [Filter Data](filter-data.md)/[Generate Codebook](generate-codebook.md)/[Apply Codebook](apply-codebook.md) |

## Developer reference

- Frontend: `components/forms/PromptManager.jsx`, `components/forms/PromptTextareaWithActions.jsx`, `frontend/src/lib/savePromptToLibrary.js`, `frontend/src/lib/apiContracts.js::EXAMPLE_PROMPTS`.
- Backend: `backend/app/api/prompt_routes.py` → `backend/app/services/prompt_service.py` (ORM-only, no repository layer).
- Endpoints: `GET /api/prompts/`, `POST /api/prompts/`, `POST /api/prompts/{id}/update`, `DELETE /api/prompts/{id}` — see [api-reference.md](../api-reference.md#prompts--backendappapiprompt_routespy).
