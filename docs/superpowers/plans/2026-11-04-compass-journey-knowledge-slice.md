# Compass to Journey and Knowledge Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user explicitly start one dynamic Journey from a confirmed Compass direction and enqueue separate job, interview-history, and learning-resource collection work.

**Architecture:** ProductStore owns user-scoped direction, Journey, task, and collection-job state. Confirmed directions enqueue only current-job collection; `POST /v1/me/directions/{direction_id}/journey` idempotently creates a Journey, three small route tasks, and the interview/learning collection jobs. React renders only returned state and preserves manual calendar creation.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest, React, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-04-direction-compass-knowledge-refresh-design.md`

## Global Constraints

- Compass membership never creates a Journey.
- A Journey starts only after an authenticated, owner-scoped user request.
- Repeated requests reuse the same Journey and collection jobs.
- No company, role, task, or resource is hard-coded before user data exists.
- Manual calendar and task-update behavior remains available.
- Interview evidence and learning resources remain separate knowledge domains.

## Review Focus

- Another owner cannot start or inspect a Journey for someone else's direction.
- Repeated clicks cannot duplicate Journeys, route tasks, or collection jobs.
- A direction with no Journey must remain visible in Compass without preparation tasks.
- Legacy manual calendar entries still render and update without a Journey entity.
- Empty collection results remain honest queued/empty states, not invented resources.

---

### Task 1: Owner-scoped Journey lifecycle and collection queue

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `tests/api/test_directions.py`
- Modify: `tests/test_product_store.py`

**Interfaces:**
- Produces: `ProductStore.start_direction_journey(owner_id, direction_id)` and `POST /v1/me/directions/{direction_id}/journey`.
- Produces dashboard `journeys` and `collection_jobs`; existing `journey` remains the task list.

- [x] Add failing tests for job collection on confirmed direction, no automatic Journey, owner isolation, idempotent Journey creation, three route tasks, and two preparation collection jobs.
- [x] Run focused tests and verify RED.
- [x] Add `journeys` and `knowledge_collection_jobs` tables plus task linkage columns.
- [x] Implement transactional direction collection and explicit Journey creation.
- [x] Add the owner-scoped API endpoint and run focused tests GREEN.

### Task 2: Compass confirmation interaction

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/compass/CompassPage.tsx`
- Modify: `frontend/src/pages/compass/CompassPage.test.tsx`

**Interfaces:**
- Consumes: dashboard `journeys`, `POST /v1/me/directions/{id}/journey`.
- Produces: confirmation-first “开始航程” action and existing-Journey navigation.

- [x] Add failing UI tests for confirmation, API call, existing-Journey state, and no duplicate action.
- [x] Run focused tests and verify RED.
- [x] Add typed contracts and confirmation interaction.
- [x] Run focused tests GREEN.

### Task 3: Dynamic Journey route and collection progress

**Files:**
- Modify: `frontend/src/data/types.ts`
- Modify: `frontend/src/pages/journey/JourneyPage.tsx`
- Modify: `frontend/src/pages/journey/JourneyPage.test.tsx`

**Interfaces:**
- Consumes: dashboard `journeys`, linked route tasks, and `collection_jobs`.
- Produces: data-driven Journey selectors, route steps, and honest collection status while retaining calendar controls.

- [x] Add failing UI tests for dynamic Journey name, three returned tasks, collection states, and manual calendar retention.
- [x] Run focused tests and verify RED.
- [x] Render route state by `journey_id` and show linked collection progress.
- [x] Run focused tests GREEN.

### Task 4: Split interview archive and learning resources

**Files:**
- Modify: `src/careerpilot/api/app.py`
- Modify: `tests/api/test_documents.py`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/knowledge/KnowledgeLayout.tsx`
- Create: `frontend/src/pages/knowledge/interview/InterviewArchivePage.tsx`
- Modify: `frontend/src/pages/knowledge/preparation/PreparationPage.tsx`
- Modify: `frontend/src/pages/knowledge/knowledge-pages.test.tsx`

**Interfaces:**
- Produces: `/v1/knowledge/interview-archive` and `/v1/knowledge/learning` with separate domain filters.
- Produces: `往年题目` and `学习资源` navigation; `/knowledge/preparation` redirects to learning.

- [x] Add failing API/UI tests proving domain separation and distinct navigation.
- [x] Run focused tests and verify RED.
- [x] Add separate endpoints, typed clients, route, and pages with provenance/trust copy.
- [x] Run focused tests GREEN.

### Task 5: Integrated verification

**Files:**
- Modify tests only after reproducing any discovered bug.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: verified Compass-to-Journey-to-knowledge vertical slice.

- [x] Run focused backend and frontend suites.
- [x] Run full Python and frontend suites plus production build.
- [x] Inspect for hard-coded directions and direct Compass-to-Journey side effects.
