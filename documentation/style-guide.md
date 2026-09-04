# Web App Style Guide

Reference for the frontend's visual identity. This is a style *reference*, not a design spec — consult it when building or touching UI so new work stays consistent with the rest of the app. Implemented in Tailwind CSS v4 via the `@theme` block in `frontend/src/index.css`.

## Identity in one line

Pure black and white, hard edges, high contrast, hover-invert interactions. No gray ramp, no rounded corners, no decorative color.

## Color

| Token | Value | Tailwind | Use |
|---|---|---|---|
| `--color-ink` | `#000000` | `bg-ink` / `text-ink` | Page background, default surface |
| `--color-paper` | `#ffffff` | `bg-paper` / `text-paper` | Default text/border, inverted surface on hover/active |
| `--color-error` | `#ff6666` | `text-error` / `border-error` | Errors, destructive actions (the *only* red used anywhere) |
| `--color-success` | `#00aa00` | `text-success` / `border-success` | Success/confirmation states |
| `--color-line` | `white @ 28%` | `border-line` | Default region border (the `Panel` edge) |
| `--color-line-soft` | `white @ 14%` | `border-line-soft` | Row dividers inside a region |
| `--color-line-strong` | `#ffffff` | `border-line-strong` | Emphasis: modals, primary actions |
| `--color-surface` | `white @ 2%` | `bg-surface` | Region fill, one step off the page |
| `--color-surface-raised` | `white @ 5%` | `bg-surface-raised` | Form fields, inset boxes |

The `line`/`surface` tokens are the named form of the white-alpha rule below --
prefer them over ad-hoc `border-paper/20`, `bg-white/5`, and friends, so a
density change is one edit rather than forty.

No other named colors exist in the palette. Two narrow, intentional exceptions:

1. **Per-code colors** in the coding table/legend — each qualitative code gets a deterministic color from a hash of its name (`getCodeColor` in `src/lib/codingUtils.js`), so codes stay visually distinguishable across a session. These are data-driven and stay as inline `style`, never Tailwind classes.
2. **White-alpha overlays** (`white/5`, `white/8`, `white/10`, `white/20`) stand in for "gray" — used for hover states, subtle elevation, disabled backgrounds, and hierarchy in dense UI (tables, tree views, accordions). Never use a literal gray hex value; always derive shade from white opacity so the palette stays anchored to black/white.

Anything else (blue buttons, gradients, off-palette reds like `#e74c3c`, gray hex ramps like `#222`/`#111`) is legacy drift being removed, not part of the system.

## Typography

- Font stack: `system-ui, -apple-system, sans-serif` everywhere (no `Arial` — that was a legacy inconsistency on a couple of pages).
- Headings: bold/semibold, sized roughly `1.5rem` → `3rem` depending on hierarchy level; page titles are centered on simple form-style pages, left-aligned on data/dashboard-style pages.
- Body copy: `1rem` default, `0.875–0.9rem` for secondary/meta text (timestamps, helper text, counts).
- Line height ~1.5 for body text.

## App shell

The app is a **fixed-height viewport**: `html`/`body` never scroll (see
`index.css`), and `App.jsx` is an `h-dvh` flex column. Every scroll region is
owned by a page or a panel. This is what lets a dense page ask for the real
remaining height instead of guessing at it with `calc(100vh - …)`.

Two components implement it, and between them they replaced a five-file shell
that stacked a centered max-width container inside global padding inside a
`border-2` panel:

- **`components/shell/PageShell.jsx`** — the one page frame. A toolbar row that
  never scrolls, above a body that does.
  - The toolbar holds the page's **only** title (left-aligned, `text-base
    font-semibold`), an optional subtitle, and every page-level action pushed
    right: the artifact picker, Compare/History/Lineage, view-mode tabs, Edit.
  - `width`: `"full"` (no cap — dense pages), `"wide"` (`max-w-[1600px]`),
    `"prose"` (`max-w-3xl` — long-form reading).
  - `scroll`: `"page"` (the body scrolls as one column) or `"fill"` (the body is
    a fixed-height box and the **child** owns scrolling — for viewport-height
    workspaces).
- **`components/shell/Panel.jsx`** — the one bordered region: a single 1px
  `border-line` edge, a `border-b` header strip, one internal scroll container.
  `padded={false}` for content that draws its own borders (tables, `CodeLegend`);
  `scroll={false}` when a child owns scrolling.

**The one-border rule:** a `Panel` never directly contains another `Panel`, and
content that already carries a border goes in an unpadded `Panel` rather than
gaining a second frame. Before this, a codebook row sat four borders deep.

**Form pages** (Import, Filter, Generate Codebook, Apply Codebook, Compare,
Summarize) all share one shape: `width="wide"`, two side-by-side `Panel`s —
source on the left, output and instructions on the right — and a centered
primary button beneath. `FormShell`'s `columns` prop provides it.

## Spacing

- Base unit is Tailwind's default 4px scale. Controls sit at `py-1.5`, panel
  padding at `p-3`/`p-4`, section gaps at `gap-3`. The half-steps (`py-1.5`,
  `py-2.5`, `gap-1.5`, `px-2.5`) are part of the scale in practice, not drift.
- Control classes live in `src/lib/uiClasses.js` (`btn`, `btnPrimary`, `btnSm`,
  `btnDanger`, `btnActive`, `input`, `inputSm`, `select`, `textarea`). Use them
  rather than declaring another local `const btnClasses = "…"`; the same button
  string had drifted into ~35 variants across ~26 files.
- The sidebar is 190px wide and hidden outright when collapsed (toggled from
  the navbar), with the active route shown as a hover-invert
  (`bg-paper text-ink`).

## Borders & corners

- Borders are always white or white-alpha. `border-line` (1px) is the default
  region edge, `border-line-soft` separates rows within a region, and solid
  `border-paper` is for inputs and table cells.
- **`border-2` is reserved for modals and primary buttons.** It used to wrap
  every panel on every page — 42 sites, applied identically whether the content
  was a two-field form or a viewport-height workspace — which is what made dense
  pages feel boxed in.
- **Corners are square — `0px` radius everywhere.** This is the one hard rule the redesign enforces strictly; the legacy app had drifted to 4–12px radii (and 50% circles on a couple of icon buttons) in different places, which this cleanup removes. The only acceptable exception is a genuinely icon-only circular button (e.g. a modal close "×"), and even those default to square unless a circle is clearly better for a tap target.

## Interaction pattern

The dominant interactive pattern is **hover-invert**: an element with a white border on black background swaps to a solid white background with black text/icon on hover (and often on active/selected state, e.g. selected tab, selected list item). Reserve non-inverting hover styles (white-alpha background tint) for dense/table contexts where a full invert per-row would be too loud.

Focus states use a visible white outline (`outline: 2px solid white; outline-offset: 2px`) — never remove focus outlines without replacing them with an equally visible alternative.

## Components

- **Buttons:** three semantic variants — primary (2px border, bold), secondary (1px border, transparent), danger (error-red fill). Two size variants (small/default; a large variant exists for prominent single actions). All hover-invert except danger, which darkens.
- **Tabs / pill selectors:** bordered pill, selected state is solid white/black invert. Used for view-mode switches, project tabs, database selector strips.
- **Tables:** bordered cells (white/white-alpha), a `sticky` header row with a heavier bottom border, hover row tint via white-alpha (not invert — inverting whole rows is too loud), truncating cells with ellipsis, and per-code color badges (black text over the code's hashed HSL color) with a hover tooltip for badges carrying notes. Columns are **not** resizable; a table lives in a `padded={false}` Panel that owns the scroll.
- **Forms:** label above input, white-bordered input on a near-black field background (`#1a1a1a`/`bg-white/5`, kept slightly off pure black so fields read as distinct from the page), placeholder text in white-alpha. Radio groups render as pill buttons (hidden native radio, `sibling:checked` invert styling) rather than native radio dots. Sliders use a white thumb/track with white-alpha rail.
- **Alerts / messages:** three variants (error/success/info), each a bordered box tinted with the variant color, or a plain centered message line for lighter-weight inline feedback.
- **Empty state (`PageEmptyState`):** every view page opens in this state, so it
  gets one size and one style regardless of the page's `width` — a centered
  `max-w-2xl` box with a fixed `min-h`, never stretched to its column. Copy
  follows **"Select a &lt;noun&gt; to view &lt;what you get&gt;"**: *a database*
  (raw or filtered), *a codebook*, *a coding*, *a summary*, *a codebook/coding
  comparison*, and *a file* on the type-agnostic pages (lineage, version
  history). Never "project file" or "coded data", and never "artifact" in UI
  copy — `artifact` is the backend's word for the version spine and stays in
  code and docs, but the user picks a **file**.
- **Modals:** centered panel, 2px white border, dark translucent black backdrop (`black/80`). One modal pattern reused everywhere — the app previously had a second, near-duplicate modal implementation for the data table's entry viewer; that's being collapsed into the single shared pattern.
- **Tree/accordion views** (codebook tree, code legend): hierarchy is communicated through indentation, connector lines, borders, and font-weight — not background color steps. This is the area most affected by the black/white cleanup, since the old implementation leaned on a multi-step gray ramp instead.
- **Tooltip:** small bordered black box, appears on hover/focus, used for the "AI-use involved" label icon and code-badge notes.

## What "minimal, sharp, intuitive" means for new UI

- Default to black background / white text / white border; introduce color only for error, success, or per-code identity — never for decoration.
- Zero border-radius by default.
- Prefer a visible border over a shadow or gradient for separating elements.
- Prefer hover-invert or white-alpha tint over any new color for interactive feedback.
- When you need visual hierarchy without color, reach for: border opacity (`line-soft` / `line` / `paper`), spacing, type weight/size — not gray fills, and not a second border around something already bordered.
- Give the page its width. A centered `max-w-4xl` column was right when a page held one short form; it is not right for a table, a tree, or a 3-pane workspace. Pick `PageShell`'s `width` from the content, and keep `prose` for text people actually read.
