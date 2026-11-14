# Episodes and Hooks Phase 2 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let Bobo remember meaningful shared experiences, surface one source-backed unfinished hook, and track only commitments it can actually perform.

**Architecture:** Build event-triggered episode and hook projections on canonical turns and exploration threads. Keep technical context compaction unchanged. Retrieval receives a structured episode/hook context; it never treats summaries as user facts.

**Tech Stack:** Python 3.12, SQLite, FastAPI, pytest, React 19, TypeScript, Vitest.

---

### Task 1: Add episode, open-loop, and commitment persistence

**Files:**
- Create: `src/careerpilot/episodes/__init__.py`
- Create: `src/careerpilot/episodes/models.py`
- Create: `src/careerpilot/episodes/service.py`
- Modify: `src/careerpilot/product_store.py`
- Create: `tests/episodes/test_service.py`

**RED:** Test the five event triggers: new exploration thread, user correction, experiment result, significant direction shift, and high-value unresolved question. Prove ordinary small talk creates no episode.

**GREEN:** Add `conversation_episodes`, `open_loops`, and `agent_commitments` with source turn ids, status, trigger reason, and owner isolation.

**Verify:** `uv run pytest tests/episodes/test_service.py -q`

**Commit:** `feat(memory): add event-triggered episodes and hooks`

### Task 2: Integrate post-turn episode projection

**Files:**
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/product_store.py`
- Modify: `tests/api/test_chat.py`

**RED:** Test that episode projection runs after canonical turn persistence, is idempotent per turn, and failure does not erase or duplicate the chat turn.

**GREEN:** Run deterministic event classification synchronously for explicit product events; leave model-generated enrichment optional and out of the request-critical path.

**Verify:** `uv run pytest tests/api/test_chat.py tests/episodes/test_service.py -q`

**Commit:** `feat(chat): project meaningful turns into episodes`

### Task 3: Recall one relevant callback safely

**Files:**
- Modify: `src/careerpilot/harness/context.py`
- Modify: `src/careerpilot/agent/prompt.py`
- Modify: `src/careerpilot/agent/service.py`
- Modify: `tests/context/test_router.py`
- Modify: `tests/agent/test_prompt.py`
- Modify: `tests/agent/test_service.py`

**RED:** Test page-aware retrieval of one recent relevant episode and at most one open loop; prove source and uncertainty labels reach the prompt and LISTEN mode does not force a career callback.

**GREEN:** Add a structured callback context section and explicit instruction that callbacks are optional observations, not facts or scripted plot.

**Verify:** `uv run pytest tests/context/test_router.py tests/agent/test_prompt.py tests/agent/test_service.py -q`

**Commit:** `feat(agent): recall source-backed career callbacks`

### Task 4: Expose hooks and commitments without card overload

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/compass/CompassPage.tsx`
- Modify: `frontend/src/pages/compass/CompassPage.test.tsx`
- Modify: `src/careerpilot/api/app.py`

**RED:** Test one inline “继续探索” affordance, commitment status, resolve/dismiss actions, and no hook section when none exists.

**GREEN:** Add progressive disclosure within the focused exploration rather than a new top-level page or a grid of cards.

**Verify:** `uv run pytest -q`; `npm test -- --run`; `npm run build`

**Commit:** `feat(compass): surface active hooks and commitments`

