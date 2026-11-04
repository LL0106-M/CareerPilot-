# Knowledge and Journey Responsive Layout Design

## Intent

Repair the broken Knowledge interview archive and Journey route layouts without changing their data contracts or turning dynamic content into fixed mock screens. The pages must keep CareerPilot's landscape, glass, editorial typography, navigation, calendar, and manual task creation while remaining readable as returned content changes.

## Goals

- Give the interview archive a full-width content surface instead of placing its only child in the rail column of a two-column dashboard.
- Present collection jobs as three independent, wrapping status cards with meaningful labels.
- Replace the absolutely positioned Journey route stops with normal-flow responsive layout.
- Bound editorial headings and content widths so 1280–2048px desktop widths and narrow screens remain balanced.
- Keep empty, loading, long-title, and three-step states honest and usable.

## Non-goals

- No new backend fields or hard-coded direction content.
- No change to Journey state transitions, calendar behavior, external-app preview, or Knowledge collection triggers.
- No redesign of the global navigation or landscape visual identity.

## Approaches

1. CSS-only patch: override the collapsed columns and manually reposition the existing absolute route nodes. Fast, but still brittle when task counts and text lengths change.
2. Responsive structure (selected): add page-specific semantic classes, render collection jobs as cards, and move route nodes into a normal-flow grid. This is slightly broader but follows backend data and removes the root cause.

## Responsive Rules

- Interview archive uses a single-column `library-dashboard--single` layout and a horizontal tools row that wraps below 760px.
- Collection status uses an auto-fit grid; every job remains a separate item and long labels wrap.
- Journey hero uses bounded widths and `clamp()` typography; actions wrap without shrinking controls into vertical strips.
- Journey story and focus action use a two-column grid on large screens, one column below 980px.
- Route steps render below the focus area in a three-column normal-flow grid, then one column on small screens. No task node uses absolute positioning.

## Acceptance

- The empty interview archive occupies the main content width and its Refresh button keeps a horizontal label.
- Three collection states render as three separate cards.
- Three route steps render in DOM order without `stop-N` positioning classes.
- Long direction and task titles wrap inside their cards.
- Existing Knowledge and Journey interactions continue to pass.
