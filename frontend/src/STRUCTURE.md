## Frontend Structure

This document inventories the main React frontend modules to support cleanup and optimization work.

### Entry & Shell

- **`main.jsx`**: React entry point mounting `App` into `#root`.
- **`App.jsx`**: Application shell with router, navbar, sidebar, and lazy-loaded route components.

### Shared Libraries

- **`lib/api.js`**: Exposes `BASE_URL`, configured Axios instance `api`, and `apiFetch` wrapper for `fetch`.
- **`lib/constants.js`**: Shared constants, including AI model options.
- **`lib/codingUtils.js`**: Utilities for coding workflows (code colors, code extraction, filtered views, parsing).

### Layout & Navigation Components

- **`components/Navbar.jsx`**: Top navigation bar, API key controls, login/logout, and sidebar toggle.
- **`components/Sidebar.jsx`**: Left-hand navigation with authenticated and anonymous link sets.
- **`components/ProtectedRoute.jsx`**: Wrapper for guarding authenticated routes (currently a simple passthrough).

### Generic UI & Form Components

- **`components/ActionForm.jsx`**: Config-driven form renderer used across pages.
- **`components/EntryModal.jsx`**: Modal dialog for inspecting individual posts or comments (container/data-fetching via `apiFetch`).
- **`components/SelectionList.jsx`**: Presentational list of selectable items (buttons) for database or project selection.
- **`components/ErrorDisplay.jsx`**: Shared presentational error component for inline error messaging.
- **`components/UploadData.jsx`**: Thin presentational wrapper around `FileUpload` used on import-related pages.
- **`components/FileUpload.jsx`**: Lower-level file upload control and helpers (container-style: handles API calls and progress).
- **`components/MarkdownView.jsx`**: Presentational markdown renderer for summaries and codebooks.

### Data & Coding Visualization Components

- **`components/DataTable.jsx`**: Generic data table (container) used by data-related pages; fetches entries and supports selection/move/delete.
- **`components/CodingTableView.jsx`**: Presentational table view for coded data with filtering and highlighting.
- **`components/HighlightedContent.jsx`**: Presentational text rendering with margin-based code highlights.
- **`components/CodeLegend.jsx`**: Presentational legend showing codes and their assigned colors.
- **`components/CodebookTree.jsx`**: Presentational tree view over codebook structures.
- **`components/CodebookManager.jsx`**: Container for codebook management flows (create, edit, apply).
- **`components/ManageDatabase.jsx`**: Container UI for database-related operations (fetching metadata, triggering maintenance endpoints).
- **`components/PromptManager.jsx`**: Container for AI prompt configuration and persistence.

### Pages – Auth & Landing

- **`pages/Landing.jsx`**: Presentational public landing page for unauthenticated users.
- **`pages/Home.jsx`**: Container-style authenticated home/dashboard (navigates to core workflows).
- **`pages/Login.jsx`**: Container auth page using shared form patterns for login.
- **`pages/Register.jsx`**: Container auth page for registration.

### Pages – Data & Projects

- **`pages/Import.jsx`**: Container import data workflow that composes `UploadData` and related controls.
- **`pages/Data.jsx`**: Container view of raw data by delegating to `DataTable`.
- **`pages/FilteredData.jsx`**: Container view of filtered data, also driven by `DataTable` with `isFilteredView`.
- **`pages/Filter.jsx`**: Container UI for configuring data filters and running filter jobs.
- **`pages/Project.jsx`**: Container project-focused view and controls.

### Pages – Codebook & Coding Workflows

- **`pages/GenerateCodebook.jsx`**: Container page to generate codebooks (often via AI/prompting) using `PromptManager` and related components.
- **`pages/ViewCodebook.jsx`**: Container/presentational hybrid to browse existing codebooks using `CodebookTree` and `MarkdownView`.
- **`pages/ApplyCodebook.jsx`**: Container page to apply a codebook to data using coding views.
- **`pages/CompareCodebook.jsx`**: Container page to compare two or more codebooks (diff-like UI).
- **`pages/ViewCoding.jsx`**: Container page that composes `CodingTableView` and highlighting.
- **`pages/CompareCoding.jsx`**: Container page to compare coding outputs across coders or runs.
- **`pages/SummarizeCoding.jsx`**: Container page to generate summaries over coded data.
- **`pages/ViewSummary.jsx`**: Presentational/container hybrid to view generated summaries (often via `MarkdownView`).

