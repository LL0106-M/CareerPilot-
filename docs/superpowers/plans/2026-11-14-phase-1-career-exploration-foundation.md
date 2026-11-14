# Career Exploration Memory Phase 1 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every successful chat produce an immutable canonical turn and make Compass a real projection of career exploration threads, nodes, and evidence instead of fixed summaries.

**Architecture:** Extend `ProductStore` additively so existing directions, branches, and dashboard consumers continue working. New chat writes create one `conversation_turns` record keyed by run id, then project accepted compass updates into exploration tables. Compass reads an aggregate `exploration_views` payload assembled from source-backed evidence and unknowns.

**Tech Stack:** Python 3.12, SQLite, FastAPI, pytest, React 19, TypeScript, Vitest.

---

### Task 1: Add canonical turn persistence

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Modify: `src/careerpilot/api/app.py`
- Test: `tests/test_product_store.py`
- Test: `tests/api/test_chat.py`

**RED:** Add tests proving one chat run creates one owner-scoped canonical turn containing user message, assistant reply, page context, support mode, intent, and run id; retries remain idempotent.

**GREEN:** Add `conversation_turns`, indexes, `record_conversation_turn` return payload, and backward-compatible writes to `conversation_messages`.

**Verify:** `uv run pytest tests/test_product_store.py tests/api/test_chat.py -q`

**Commit:** `feat(memory): persist canonical conversation turns`

### Task 2: Add the career exploration graph store

**Files:**
- Create: `src/careerpilot/exploration/__init__.py`
- Create: `src/careerpilot/exploration/models.py`
- Create: `src/careerpilot/exploration/service.py`
- Modify: `src/careerpilot/product_store.py`
- Create: `tests/exploration/test_service.py`
- Modify: `tests/test_product_store.py`

**RED:** Add tests for owner isolation, flexible node types, raw/canonical labels, parent and contextual edges, support/counter/unknown evidence, and idempotent projection from one compass batch.

**GREEN:** Add `exploration_threads`, `career_nodes`, `career_edges`, and `career_evidence`; implement a deterministic projection service that maps existing accepted direction/branch/profile/evidence records without deleting legacy data.

**Verify:** `uv run pytest tests/exploration/test_service.py tests/test_product_store.py -q`

**Commit:** `feat(compass): add career exploration graph`

### Task 3: Replace fixed Compass summaries with evidence-backed views

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/compass/CompassPage.tsx`
- Modify: `frontend/src/pages/compass/CompassPage.test.tsx`
- Modify: `tests/api/test_memory_dashboard.py`

**RED:** Add API and UI tests for empty state, a broad unsplit direction, a nested role/context branch, real supporting/counter evidence, and an unknown derived from stored evidence rather than template text.

**GREEN:** Return `exploration_views` while keeping legacy fields; render one focused exploration at a time with progressive disclosure and links to source details.

**Verify:** `uv run pytest tests/api/test_memory_dashboard.py -q`; `npm test -- --run src/pages/compass/CompassPage.test.tsx`

**Commit:** `feat(compass): render evidence-backed exploration views`

### Task 4: Phase 1 regression and migration safety

**Files:**
- Modify: `tests/test_product_store.py`
- Modify: `docs/architecture/` only if behavior differs from the accepted design

**RED/GREEN:** Add a legacy-database fixture and prove initialization migrates additively, old dashboards still load, and repeated projection creates no duplicates.

**Verify:** `uv run pytest -q`; `npm test -- --run`; `npm run build`

**Commit:** `test(memory): cover exploration migration and regressions`

