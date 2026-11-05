# Journey Target Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render Journey navigation as job direction → company → business line and keep frontend and backend target identity in sync.

**Architecture:** Enrich the existing Journey branch contract from Compass branch data and repair target signals that lack a direction binding. Build a presentation-only grouping layer in React so historical duplicate directions do not produce duplicate selectors while stored rows remain untouched.

**Tech Stack:** Python 3.12, SQLite, FastAPI, React 19, TypeScript, Vitest, Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-11-05-journey-target-hierarchy-design.md`

## Global Constraints

- Navigation levels are job direction, company, and business line.
- `综合路径` and `通用主线` must not appear as navigation controls.
- Existing database rows must not be deleted.
- Existing API routes remain backward compatible.
- Every production behavior change follows RED → GREEN TDD.

## Review Focus

- A target mentioned in a different conversation still binds to the matching job direction.
- Historical accepted target signals without bindings are repaired idempotently.
- Duplicate same-title Journeys render as one direction without dropping target branches.
- Multiple companies and multiple business lines under one company switch independently.
- Legacy branch payloads without company/business fields remain understandable.

---

### Task 1: Backend target identity contract

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Test: `tests/test_product_store.py`

**Interfaces:**
- Produces: dashboard `journey_branches[]` fields `company`, `business`, `role`, and `location`.
- Produces: target-to-direction fallback matching used by current writes and historical repair.

- [ ] Add a failing store test proving a target in a different conversation binds by role and dashboard branches expose target identity.
- [ ] Run the focused test and confirm it fails because no direction/branch identity is returned.
- [ ] Implement normalized role/label fallback and enriched Journey branch reads.
- [ ] Add a failing reopen test for an old explicit unbound target signal.
- [ ] Implement idempotent historical target repair without deleting existing rows.
- [ ] Run `tests/test_product_store.py tests/api/test_directions.py tests/api/test_journey.py` and confirm they pass.

### Task 2: Three-level Journey navigation

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/journey/JourneyPage.tsx`
- Modify: `frontend/src/styles/pages.css`
- Test: `frontend/src/pages/journey/JourneyPage.test.tsx`

**Interfaces:**
- Consumes: enriched `JourneyBranch` target identity from Task 1.
- Produces: one direction selector plus company and business-line selectors.

- [ ] Replace the existing common/target branch test with a failing test for direction → company → business navigation, duplicate Journey collapse, and visible context.
- [ ] Run the focused Vitest file and confirm failure because the existing UI renders `综合路径` / `通用主线`.
- [ ] Extend the TypeScript contract and implement stable direction grouping, company grouping, business selection, and contextual task composition.
- [ ] Add responsive styling within the existing visual system.
- [ ] Run the Journey page tests and confirm they pass.

### Task 3: Cross-layer verification

**Files:**
- Modify only if verification exposes an integration defect.

**Interfaces:**
- Consumes: Tasks 1 and 2 contracts.
- Produces: verified production build and regression coverage.

- [ ] Run the relevant backend suite.
- [ ] Run the full frontend test suite, typecheck, and production build.
- [ ] Run the full Python test suite and report any unrelated failures by name.
- [ ] Review the diff for owner scoping, idempotency, duplicate keys, and legacy payload fallback.
