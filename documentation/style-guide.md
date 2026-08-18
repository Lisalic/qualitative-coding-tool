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

No other named colors exist in the palette. Two narrow, intentional exceptions:

1. **Per-code colors** in the coding table/legend — each qualitative code gets a deterministic color from a hash of its name (`getCodeColor` in `src/lib/codingUtils.js`), so codes stay visually distinguishable across a session. These are data-driven and stay as inline `style`, never Tailwind classes.
2. **White-alpha overlays** (`white/5`, `white/8`, `white/10`, `white/20`) stand in for "gray" — used for hover states, subtle elevation, disabled backgrounds, and hierarchy in dense UI (tables, tree views, accordions). Never use a literal gray hex value; always derive shade from white opacity so the palette stays anchored to black/white.

Anything else (blue buttons, gradients, off-palette reds like `#e74c3c`, gray hex ramps like `#222`/`#111`) is legacy drift being removed, not part of the system.

## Typography

- Font stack: `system-ui, -apple-system, sans-serif` everywhere (no `Arial` — that was a legacy inconsistency on a couple of pages).
- Headings: bold/semibold, sized roughly `1.5rem` → `3rem` depending on hierarchy level; page titles are centered on simple form-style pages, left-aligned on data/dashboard-style pages.
- Body copy: `1rem` default, `0.875–0.9rem` for secondary/meta text (timestamps, helper text, counts).
- Line height ~1.5 for body text.

## Spacing & layout

- Base spacing unit follows Tailwind's default 4px scale; most component padding lands on `4`/`6`/`8` (16/24/32px), form gaps on `2`–`3` (8–12px).
- Page shell: sticky top nav + collapsible left sidebar + main content area, consistent across every route.
- Tool pages (Import/Filter/Generate/Apply/Compare/Summarize) share one layout shell (`ToolPage`/`ToolPageShell`/`ToolPageBody`/`ToolPanelHost`): a centered container holding a bordered panel, sometimes split into a form column and a preview/data column.

## Borders & corners

- Borders are always white (or white-alpha for lighter separators): `1px` for standard dividers/inputs/table cells, `2px` for emphasized panels and primary actions.
- **Corners are square — `0px` radius everywhere.** This is the one hard rule the redesign enforces strictly; the legacy app had drifted to 4–12px radii (and 50% circles on a couple of icon buttons) in different places, which this cleanup removes. The only acceptable exception is a genuinely icon-only circular button (e.g. a modal close "×"), and even those default to square unless a circle is clearly better for a tap target.

## Interaction pattern

The dominant interactive pattern is **hover-invert**: an element with a white border on black background swaps to a solid white background with black text/icon on hover (and often on active/selected state, e.g. selected tab, selected list item). Reserve non-inverting hover styles (white-alpha background tint) for dense/table contexts where a full invert per-row would be too loud.

Focus states use a visible white outline (`outline: 2px solid white; outline-offset: 2px`) — never remove focus outlines without replacing them with an equally visible alternative.

## Components

- **Buttons:** three semantic variants — primary (2px border, bold), secondary (1px border, transparent), danger (error-red fill). Two size variants (small/default; a large variant exists for prominent single actions). All hover-invert except danger, which darkens.
- **Tabs / pill selectors:** bordered pill, selected state is solid white/black invert. Used for view-mode switches, project tabs, database selector strips.
- **Tables:** bordered cells (white/white-alpha), header row with a heavier bottom border, hover row tint via white-alpha (not invert — inverting whole rows is too loud), resizable columns via a thin drag handle, truncating cells with ellipsis, and per-code color badges (black text over the code's hashed HSL color) with a hover tooltip for badges carrying notes.
- **Forms:** label above input, white-bordered input on a near-black field background (`#1a1a1a`/`bg-white/5`, kept slightly off pure black so fields read as distinct from the page), placeholder text in white-alpha. Radio groups render as pill buttons (hidden native radio, `sibling:checked` invert styling) rather than native radio dots. Sliders use a white thumb/track with white-alpha rail.
- **Alerts / messages:** three variants (error/success/info), each a bordered box tinted with the variant color, or a plain centered message line for lighter-weight inline feedback.
- **Modals:** centered panel, 2px white border, dark translucent black backdrop (`black/80`). One modal pattern reused everywhere — the app previously had a second, near-duplicate modal implementation for the data table's entry viewer; that's being collapsed into the single shared pattern.
- **Tree/accordion views** (codebook tree, code legend): hierarchy is communicated through indentation, connector lines, borders, and font-weight — not background color steps. This is the area most affected by the black/white cleanup, since the old implementation leaned on a multi-step gray ramp instead.
- **Tooltip:** small bordered black box, appears on hover/focus, used for the "AI-use involved" label icon and code-badge notes.

## What "minimal, sharp, intuitive" means for new UI

- Default to black background / white text / white border; introduce color only for error, success, or per-code identity — never for decoration.
- Zero border-radius by default.
- Prefer a visible border over a shadow or gradient for separating elements.
- Prefer hover-invert or white-alpha tint over any new color for interactive feedback.
- When you need visual hierarchy without color, reach for: border weight (1px vs 2px), spacing, type weight/size — not gray fills.
