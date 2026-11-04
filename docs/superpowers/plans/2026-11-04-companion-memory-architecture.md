# Companion Memory Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first governed companion-memory phase: safe admission and correction, correct post-turn usage accounting, and a real user-controlled memory screen.

**Architecture:** Keep `MemoryService` and `SqliteUnifiedMemoryStore` as the canonical boundary. Strengthen lifecycle operations transactionally, keep retrieval read-only, and connect the React memory page directly to the authenticated `/v1/me/memories` endpoints.

**Tech Stack:** Python 3.12, SQLite, FastAPI, pytest, React, TypeScript, Vitest/Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-04-companion-memory-architecture-design.md`

## Global Constraints

- Preserve all unrelated dirty-worktree changes.
- Current user statements override historical memory; inferred content never silently becomes confirmed.
- Transient distress and negative self-judgment must not enter active long-term memory.
- MemOS remains non-authoritative and disabled unless semantic evaluation demonstrates a need.
- Every production behavior change follows RED → GREEN TDD.

## Review Focus

- A sentence beginning with "我有点" must not become a durable fact.
- Correcting one preference must not supersede other preferences sharing generic words.
- Raising sensitivity must not leave an ordinary active copy retrievable after confirmation.
- A failed/cancelled answer must not be recorded as memory usage.
- UI lifecycle controls must change canonical server state, not local visual state only.

---

### Task 1: Safe admission and correction

**Files:**
- Modify: `tests/memory/test_write_policy.py`
- Modify: `tests/memory/test_memory_service.py`
- Modify: `src/careerpilot/memory/write_policy.py`
- Modify: `src/careerpilot/memory/service.py`
- Modify: `src/careerpilot/memory/unified_store.py`

**Interfaces:**
- Produces: conservative `MemoryWritePolicy.extract`; targeted correction; atomic sensitive replacement confirmation.
- Consumes: existing `MemoryRecord`, status transitions, revisions, evidence, and relations.

- [ ] Add failing tests for transient distress, profile-update wording, unrelated-preference preservation, sensitivity-only upgrade, and replacement confirmation.
- [ ] Run focused tests and confirm the expected failures.
- [ ] Implement minimal admission and transactional lifecycle changes.
- [ ] Run focused memory tests and confirm they pass.

### Task 2: Post-success usage accounting

**Files:**
- Modify: `tests/harness/test_contextual_memory_pipeline.py`
- Modify: `tests/agent/test_service.py` or the existing AgentService test module
- Modify: `src/careerpilot/harness/context.py`
- Modify: `src/careerpilot/agent/service.py`

**Interfaces:**
- Consumes: retrieved `CompiledContext.memories` and concrete `run_id`.
- Produces: usage records only after a successful verified response.

- [ ] Add a failing test proving context compilation does not record usage.
- [ ] Add a failing service test proving completed runs do record usage with the run ID.
- [ ] Move usage recording from compilation to the post-response learn phase.
- [ ] Run harness and agent tests.

### Task 3: Canonical memory UI

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/data/types.ts`
- Modify: `frontend/src/pages/memory/MemoryPage.tsx`
- Create: `frontend/src/pages/memory/MemoryPage.test.tsx`

**Interfaces:**
- Consumes: `/v1/me/memories`, `/confirm`, `/pause`, `/resume`, `PATCH`, and `DELETE`.
- Produces: authenticated list, filter, edit, lifecycle controls, loading/error/empty states.

- [ ] Add failing UI tests against complete API payload fixtures.
- [ ] Add typed API methods and canonical memory types.
- [ ] Replace demo/local state with server-backed controls.
- [ ] Run focused frontend tests and type/build checks.

### Task 4: Integrated verification

**Files:**
- Modify tests only if a newly discovered integration bug first receives a failing regression test.

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: verified backend and frontend memory lifecycle.

- [ ] Run the full Python suite.
- [ ] Run the full frontend suite and production build.
- [ ] Inspect the final diff for unrelated changes and privacy regressions.
