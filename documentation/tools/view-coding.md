# View Coding

## Purpose

Inspect and edit a coding artifact — as raw text or as an editable table of post/code/evidence rows — and save changes back or as a new duplicate.

## Where to find it

Sidebar → View Coding (Views group), or `/coding-view` → `pages/ViewCoding.jsx`. This is the largest workspace in the app (`useViewCodingPage.js` is ~470 lines).

## Prerequisites

At least one coding artifact (from [Apply Codebook](apply-codebook.md), or a saved [Compare Codings](compare-codings.md) result). No API key needed.

## Inputs

| Control | Notes |
|---|---|
| Project scope bar + coding picker | `ArtifactSelector` over `GET /api/my-files/?file_type=coding` |
| View mode tabs | "Text View" or "Table View" |
| Table rows | per post: Post ID, and repeatable Code / Evidence / Notes triples; code entry is a union of codes already in the data and codes in the codebook tree |
| Codebook tree (editable) | renaming a code here propagates the rename into every row that uses it |
| Save panel | Name field (required), "Save and Overwrite" or "Save and Duplicate" |
| Column picker | show/hide Post ID (hidden by default), Title, Content, Codes Applied; column widths are resizable |

Column visibility/width preferences persist in `localStorage` (`viewCoding.tableColumnVisibility.v2`, `viewCoding.tableColumnWidths.v1`).

## What happens on submit

All direct (non-job) calls:

- Load: `GET /api/coded-data?coded_id=...` → `{coded_data, codebook_tree, systemprompt, userprompt}`; `POST /api/post-contents/` (`{schema, post_ids}`) resolves post titles/content from the parent raw/filtered file for display.
- Save and Overwrite: `POST /api/save-file-coded-data/` (`schema_name`, `content`, `display_name`, plus a legacy `codebook_text` field that the backend now intentionally ignores).
- Save and Duplicate: `POST /api/save-file-coded-data-duplicate/` (`source_schema_name`, `content`, `display_name`, `codebook_text`) — creates a new coding file and switches the view to it.

Before either save, rows are validated client-side (`normalizeParsedCodingRows`): the table can't be empty, every row needs a Post ID, and every code needs matching evidence (both required if either is present).

## Output

Overwrite mutates the existing coding artifact's `artifact_content`; Duplicate creates a new `coding` File with cloned `file_dependencies` and content. Save state shows a transient success message that auto-clears after ~2.4s.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Name is required." | Blank name in the save panel |
| "Cannot save an empty coding table." | No rows in the table |
| A code/evidence pair won't save | Both a code and its evidence are required together — one without the other is rejected client-side |
| Row content resolves to blank | `post-contents` lookup depends on the coding file's recorded parent (`parent_files`); if that lineage is missing, titles/content can't be resolved |

## Developer reference

- Frontend: `pages/ViewCoding.jsx`, `components/coding-table/workspace/useViewCodingPage.js`, `CodingWorkspaceSection.jsx`, `CodingProjectScopeBar.jsx`, `CodingEditActionsBar.jsx`, `CodingSavePanel.jsx`; table: `CodingTableView.jsx`, `CodingTableHeader.jsx`, `CodingTableRow.jsx`, `CodingTableEditRow.jsx`, `CodeLegend.jsx`, `HighlightedContent.jsx`, `ColumnPicker.jsx`, `useCodingTableData.js`, `useColumnSettings.js`, `useColumnResize.js`; parsing/serialization: `frontend/src/lib/codingUtils.js` (`parseCodingData`, `formatCodingData`, `serializeCodebookTreeToText`), `codingViewHelpers.js`.
- Backend: `backend/app/api/coding_routes.py` (`GET /coded-data`, `POST /save-file-coded-data/`, `POST /save-file-coded-data-duplicate/`) → `backend/app/services/coding_service.py` → `backend/app/repositories/artifact_content_repo.py`.
- Endpoints — see [api-reference.md](../api-reference.md#coding--backendappapicoding_routespy).
