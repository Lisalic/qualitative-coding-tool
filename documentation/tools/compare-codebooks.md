# Compare Codebooks

## Purpose

Compare two codebooks with a deterministic, no-LLM structural diff —
added/removed/renamed codes, family changes — computed directly from
each codebook's stored codes. No API key, no background job.

**Retired:** this page used to also offer an optional LLM-generated
narrative synthesis (`POST /api/compare-codebooks/`, job-backed). That
creation path has been removed; any `codebook_comparison` artifact it
already produced is still viewable (see [View Codebook](view-codebook.md)),
but nothing creates new ones this way any more.

## Where to find it

Sidebar → Compare Codebook (pipeline group), or `/compare-codebook` →
`pages/CompareCodebook.jsx` → `components/compare/ComparePageContainer.jsx`
with `mode="codebook"`.

This shares one implementation with [Compare Codings](compare-codings.md)
— `ComparePageContainer`'s `CONFIG_BY_MODE` is the only difference
between the two pages. See [architecture.md](../architecture.md) for the
shared plumbing.

## Prerequisites

At least two codebook artifacts. No API key needed.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Codebook A | yes | from `GET /api/my-files/?file_type=codebook` |
| Codebook B | yes | when arriving with a preselected A (e.g. from View Codebook), B auto-picks the first other item |

## What happens

As soon as both A and B are selected, `useComparePageData.js` calls
`GET /api/comparison/codebooks?file_a=...&file_b=...` (`comparison_routes.py`
→ `comparison_service.compare_codebooks`) and renders the result via
`ComputedComparisonResults`. No submit step, no job to poll.

## Output

A structural diff (`backend/app/core/codebook_diff.py::diff_codes`, keyed
on `code_uid` for stable-identity matching across renames): added,
removed, renamed, redefined, moved, reordered, and unchanged codes, plus
unrelated-history detection when the two codebooks share no code
lineage. Swap A/B to view the diff from the other direction --
reversibility is a tested invariant.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Nothing renders | One of the two selects is still empty |
| Error banner | The comparison request failed — check both files are owned codebook artifacts |

## Developer reference

- Frontend: `pages/CompareCodebook.jsx`, `components/compare/ComparePageContainer.jsx`, `CompareDualSelectPanel.jsx`, `ComputedComparisonResults.jsx`, `useComparePageData.js`.
- Backend: `backend/app/api/comparison_routes.py::GET /comparison/codebooks` → `backend/app/services/comparison_service.py::compare_codebooks`.
- No storage written — this is a read-only, computed-on-request diff.
- Endpoint: `GET /api/comparison/codebooks` — see [api-reference.md](../api-reference.md).
