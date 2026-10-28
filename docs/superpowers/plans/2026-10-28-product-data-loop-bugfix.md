# Product Data Loop Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicit chat ideas appear in Compass, make Compass actions create Journey work, render Journey's three views as genuinely distinct views, and let newly collected preparation resources appear in Knowledge.

**Architecture:** Keep unified memory as the source of truth for chat-derived ideas and hypotheses, and keep `ProductStore` as the owner-scoped action/journey projection. Persist explicitly collected public preparation links into the RAG store and expose indexed preparation documents through the existing API.

**Tech Stack:** FastAPI, SQLite, React, TypeScript, Vitest, pytest.

**Specs:** `docs/superpowers/specs/2026-10-25-careerpilot-compass-page-design.md`, `docs/superpowers/specs/2026-10-25-careerpilot-journey-page-design.md`, `docs/superpowers/specs/2026-10-25-careerpilot-knowledge-library-page-design.md`

## Global Constraints

- Do not infer stable preferences or facts from ambiguous chat text.
- Only explicit idea language is captured automatically.
- Journey remains opt-in: an idea or hypothesis becomes a task only after the user clicks the verification action.
- Public web sources require a real URL and retain source metadata.
- Preserve owner scoping for memories and journey tasks.

## Review Focus

- Hypothesis IDs returned by the dashboard must be accepted by decision and verification endpoints.
- Repeating the same explicit idea must not create duplicate memories.
- Relative and non-date journey due values must not be placed on arbitrary calendar days.
- Preparation resources with missing URLs must not enter the library.
- Curated resources remain visible when the backend has no collected preparation material.

---

### Task 1: Canonical Compass interactions

**Files:**
- Modify: `src/careerpilot/memory/write_policy.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/product_store.py`
- Test: `tests/api/test_memory_dashboard.py`
- Test: `tests/memory/test_write_policy.py`

**Interfaces:**
- Produces: canonical dashboard idea/hypothesis payloads and verification tasks created from canonical memory records.

- [ ] Add failing tests for explicit chat idea extraction, canonical hypothesis confirmation, and idea/hypothesis task creation.
- [ ] Run focused tests and verify the current store mismatch fails.
- [ ] Implement the minimal canonical-memory endpoints and owner-scoped task projection.
- [ ] Run focused tests and verify they pass.

### Task 2: Compass idea actions and Journey calendar

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/compass/CompassPage.tsx`
- Modify: `frontend/src/pages/compass/CompassPage.test.tsx`
- Modify: `frontend/src/pages/journey/JourneyPage.tsx`
- Modify: `frontend/src/pages/journey/JourneyPage.test.tsx`
- Modify: `frontend/src/styles/pages.css`

**Interfaces:**
- Consumes: Task 1 idea verification endpoint.
- Produces: an explicit action on chat-derived ideas and a real month view keyed by task due dates.

- [ ] Add failing UI tests for idea-to-journey interaction, dated task placement, undated task separation, and distinct view headings.
- [ ] Run focused tests and verify they fail for missing behavior.
- [ ] Implement minimal UI and date parsing.
- [ ] Run focused tests and verify they pass.

### Task 3: Updateable preparation library

**Files:**
- Modify: `src/careerpilot/rag/store.py`
- Modify: `src/careerpilot/rag/tool.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/knowledge/preparation/PreparationPage.tsx`
- Test: `tests/rag/test_agentic_tool.py`
- Test: `tests/api/test_documents.py`
- Test: `frontend/src/pages/knowledge/knowledge-pages.test.tsx`

**Interfaces:**
- Produces: `list_documents_for_domains(...)`, explicit-search web-source ingestion, `/v1/knowledge/preparation`, and live preparation resources in the UI.

- [ ] Add failing backend and frontend tests for saving and listing URL-backed resources.
- [ ] Run focused tests and verify the endpoint/UI are currently static.
- [ ] Implement URL-deduplicated RAG ingestion, listing, and frontend merge with curated fallback.
- [ ] Run focused tests and verify they pass.

### Task 4: Regression verification

**Files:**
- Test only.

**Interfaces:**
- Consumes: Tasks 1-3.

- [ ] Run focused frontend and backend suites.
- [ ] Run the complete frontend tests and build.
- [ ] Run the complete backend suite and report any unrelated baseline failures by name.
