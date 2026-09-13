# Compare Codings

## Purpose

Compare two coding artifacts with a deterministic, no-LLM diff of their
classifications — recoded/newly-coded/newly-uncoded rows, per-code
counts and deltas, applied/removed evidence — computed directly from
each artifact's `coding_entries`. No API key, no background job.

**Retired:** this page used to also offer an optional LLM-generated
narrative synthesis (`POST /api/compare-codings/`, job-backed). That
creation path has been removed; any `coding_comparison` artifact it
already produced is still viewable (see [View Coding](view-coding.md)),
but nothing creates new ones this way any more.

## Where to find it

Sidebar → Compare Coding (pipeline group), or `/compare-coding` →
`pages/CompareCoding.jsx` → `components/compare/ComparePageContainer.jsx`
with `mode="coding"`.

Shares one implementation with [Compare Codebooks](compare-codebooks.md)
— see that page and [architecture.md](../architecture.md) for the shared
plumbing (`ComparePageContainer`'s `CONFIG_BY_MODE`).

## Prerequisites

At least two coding artifacts. No API key needed.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Coding A | yes | from `GET /api/my-files/?file_type=coding` |
| Coding B | yes | auto-picks the first other item when A arrives preselected |

## What happens

As soon as both A and B are selected, `useComparePageData.js` calls
`GET /api/comparison/codings?file_a=...&file_b=...` (`comparison_routes.py`
→ `comparison_service.compare_codings`) and renders the result via
`ComputedComparisonResults`. No submit step, no job to poll.

## Output

A classification diff (`backend/app/core/coding_diff.py::diff_coding_entries`):
total/coded row counts on each side, matching rows, rows recoded /
newly coded / newly uncoded, and per-code frequency deltas with
applied/removed evidence. Swap A/B to view the diff from the other
direction — reversibility is a tested invariant.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Nothing renders | One of the two selects is still empty |
| Error banner | The comparison request failed — check both files are owned coding artifacts |

## Developer reference

- Frontend: `pages/CompareCoding.jsx`, `components/compare/ComparePageContainer.jsx`, `CompareDualSelectPanel.jsx`, `ComputedComparisonResults.jsx`, `useComparePageData.js`.
- Backend: `backend/app/api/comparison_routes.py::GET /comparison/codings` → `backend/app/services/comparison_service.py::compare_codings`.
- No storage written — this is a read-only, computed-on-request diff.
- Endpoint: `GET /api/comparison/codings` — see [api-reference.md](../api-reference.md).
