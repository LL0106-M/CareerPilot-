# Knowledge and Journey Responsive Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the data-driven Knowledge and Journey layouts so empty states, collection progress, long titles, and route steps remain readable across desktop and narrow viewports.

**Architecture:** Keep existing API contracts and page behaviors. Add semantic page modifiers and replace Journey's absolute route decoration with normal-flow cards; CSS controls responsive composition and bounded typography.

**Tech Stack:** React 19, TypeScript, CSS, Vitest, Testing Library, Vite.

**Spec:** `docs/superpowers/specs/2026-11-04-responsive-knowledge-journey-design.md`

## Global Constraints

- Preserve dynamic backend-driven content and existing interactions.
- Preserve the global navigation, landscape, calendar, and manual task creation.
- Do not hard-code directions, jobs, interview questions, or learning resources.
- Do not use absolute positioning for dynamic Journey route nodes.

## Review Focus

- Empty interview archives must not inherit a missing rail column.
- Long direction and task names must wrap without horizontal page overflow.
- Missing or additional collection jobs must not collapse the layout.
- Narrow screens must retain readable buttons and DOM-order route steps.
- Calendar and external-app actions must remain unchanged.

---

### Task 1: Lock the broken structures with tests

**Files:**
- Modify: `frontend/src/pages/knowledge/knowledge-pages.test.tsx`
- Modify: `frontend/src/pages/journey/JourneyPage.test.tsx`

**Interfaces:**
- Consumes: existing page components and dashboard fixtures.
- Produces: semantic layout contract for single-column archive, collection cards, and normal-flow route steps.

- [x] Add assertions for `library-dashboard--single`, horizontal Refresh content, three collection cards, and an ordered `journey-route` list with no `stop-N` classes.
- [x] Run focused tests and verify RED.

### Task 2: Implement responsive page structure

**Files:**
- Modify: `frontend/src/pages/knowledge/interview/InterviewArchivePage.tsx`
- Modify: `frontend/src/pages/journey/JourneyPage.tsx`
- Modify: `frontend/src/styles/pages.css`

**Interfaces:**
- Consumes: existing `InterviewArchiveResource`, `KnowledgeCollectionJob`, and `JourneyItem` data.
- Produces: normal-flow page markup and responsive CSS with the same user actions.

- [x] Add the single-column archive modifier and readable tool/empty-state structure.
- [x] Render collection jobs as labeled status cards with status-specific classes.
- [x] Render Journey steps in a semantic ordered list below the two-column story/focus grid.
- [x] Add bounded desktop and narrow-screen CSS without fixed data assumptions.
- [x] Run focused tests and verify GREEN.

### Task 3: Visual and integrated verification

**Files:**
- Modify tests only if a reproduced defect requires it.

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: verified production bundle and refreshed ngrok deployment.

- [x] Run the full frontend suite and production build.
- [x] Restart the production server so the latest bundle is served.
- [x] Inspect Knowledge and Journey at the current desktop viewport and one narrow viewport.
- [x] Run backend smoke health checks; public ngrok exposure remains an explicit user-authorized deployment step.
