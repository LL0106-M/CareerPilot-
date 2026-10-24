# Unified Memory, Ideas, Dreaming, and Compaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the authoritative local memory backend, first-class Idea lifecycle, dual-output
Dreaming, and bounded conversation compaction needed before the unified frontend is developed.

**Architecture:** SQLite remains authoritative. Canonical memories own provenance, privacy, and
retrieval; linked Idea projections own maturation toward governed actions; Dreaming emits a
reviewable DailyReview plus versioned MemoryPatch; the Harness compacts active context without
altering the exact Session log.

**Tech Stack:** Python 3.12, SQLite, FastAPI, pytest, existing CareerPilot Harness and action policy.

**Spec:** `docs/superpowers/specs/2026-10-24-unified-memory-backend-design.md`

## Global Constraints

- No frontend work in this plan.
- Every persistence query and join is owner-scoped.
- SQLite works without MemOS or network access.
- Candidate, paused, superseded, deleted, expired, and unauthorized records never enter ordinary
  Agent context.
- Ideas cannot grant or execute external actions.
- Dreaming and compaction outputs never silently become active long-term memory.

## Review Focus

- A guessed idea without candidate-capture authorization must remain ephemeral.
- A sensitive idea must remain candidate even when stated explicitly.
- A Dreaming failure must not partially mutate canonical memory or the published DailyReview.
- Compaction must keep pending confirmations and complete tool-call/result pairs intact.
- Cross-owner IDs must behave as missing and must not reveal existence through errors.

---

### Task 1: Canonical memory domain and SQLite store

**Files:**
- Create: `src/careerpilot/memory/models.py`
- Create: `src/careerpilot/memory/unified_store.py`
- Create: `tests/memory/test_unified_store.py`

**Interfaces:**
- Produces: immutable `MemoryRecord`, `MemoryEvidence`, `MemoryUsage`, enums, and
  `SqliteUnifiedMemoryStore` CRUD/lifecycle/revision methods used by later tasks.

- [ ] Write failing store tests for owner isolation, valid transitions, optimistic conflicts,
  expiry, soft deletion, evidence, revisions, and transactional usage.
- [ ] Run `pytest tests/memory/test_unified_store.py -q` and verify failures are caused by missing
  domain/store code.
- [ ] Implement the minimal schema, models, and transactions defined in the spec.
- [ ] Run the focused tests and verify they pass.
- [ ] Commit the task.

### Task 2: Memory service, admission, and local retrieval

**Files:**
- Create: `src/careerpilot/memory/service.py`
- Create: `src/careerpilot/memory/admission.py`
- Create: `tests/memory/test_memory_service.py`

**Interfaces:**
- Consumes: Task 1 store and models.
- Produces: `MemoryService`, `MemoryQueryPurpose`, `MemoryContextBundle`, and admission protocols.

- [ ] Write failing service tests for explicit/proposed admission, sensitivity escalation,
  duplicate evidence, contradiction candidates, retrieval eligibility, ranking, and MemOS-free
  operation.
- [ ] Run the focused test and verify expected failures.
- [ ] Implement the smallest policy/service/search behavior that satisfies the tests.
- [ ] Run the focused tests and verify they pass.
- [ ] Commit the task.

### Task 3: First-class Idea lifecycle

**Files:**
- Create: `src/careerpilot/memory/ideas.py`
- Create: `tests/memory/test_ideas.py`

**Interfaces:**
- Consumes: Task 2 `MemoryService` and Task 1 transaction/store primitives.
- Produces: `IdeaItem`, `IdeaStage`, `StorageAuthorization`, and `IdeaService` capture, query,
  transition, next-step, and action-link methods.

- [ ] Write failing tests for authorized explicit capture, unauthorized inferred capture,
  sensitive candidates, owner isolation, duplicate capture, version conflicts, stage transitions,
  and action references that cause no tool invocation.
- [ ] Run the focused test and verify expected failures.
- [ ] Implement atomic canonical-memory plus Idea-projection persistence.
- [ ] Run the focused tests and verify they pass.
- [ ] Commit the task.

### Task 4: Dual-output Dreaming

**Files:**
- Modify: `src/careerpilot/memory/dreaming.py`
- Modify: `src/careerpilot/memory/dreaming_llm.py`
- Modify: `src/careerpilot/memory/cognitive_store.py`
- Create: `src/careerpilot/memory/daily_review.py`
- Modify: `tests/memory/test_dreaming.py`
- Modify: `tests/memory/test_dreaming_llm.py`
- Modify: `tests/memory/test_cognitive_store.py`

**Interfaces:**
- Consumes: canonical memory and Idea services.
- Produces: immutable evidence windows, `DailyReview`, validated `MemoryPatch` sets, and atomic
  publish/apply behavior.

- [ ] Write failing tests for local-day selection, wins/ideas/blockers/open-loops/next-step output,
  provenance, review edits, shadow diffs, confirmation gates, rollback, and failure atomicity.
- [ ] Run the focused Dreaming tests and verify expected failures.
- [ ] Implement the dual-output processor while preserving three-attempt jobs.
- [ ] Run the focused tests and verify they pass.
- [ ] Commit the task.

### Task 5: Context window manager

**Files:**
- Create: `src/careerpilot/harness/context_window.py`
- Modify: `src/careerpilot/harness/session.py`
- Modify: `src/careerpilot/harness/runtime.py`
- Create: `tests/harness/test_context_window.py`
- Modify: `tests/harness/test_runtime.py`

**Interfaces:**
- Consumes: exact Session history and optional pre-compaction admission callback.
- Produces: `ContextWindowManager.compile(...)`, persisted `SessionCompaction`, and a bounded model
  message list.

- [ ] Write failing tests for threshold behavior, tool-result clearing, recent verbatim turns,
  protected state, atomic tool pairs, source hashes, failure fallback, and summary non-admission.
- [ ] Run the focused tests and verify expected failures.
- [ ] Implement deterministic assembly plus a pluggable summarizer protocol.
- [ ] Run focused Harness tests and verify they pass.
- [ ] Commit the task.

### Task 6: Owner-scoped APIs and Agent integration

**Files:**
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/agent/context.py`
- Modify: `src/careerpilot/agent/service.py`
- Create: `tests/api/test_memories.py`
- Create: `tests/api/test_ideas.py`
- Create: `tests/api/test_daily_reviews.py`
- Modify: `tests/agent/test_service.py`

**Interfaces:**
- Consumes: Tasks 2-5 services.
- Produces: stable `/v1/me/memories`, `/ideas`, and `/daily-reviews` APIs plus attributable Agent
  retrieval.

- [ ] Write failing API/Agent tests for signed-owner derivation, validation, conflicts, filters,
  authorization receipts, active-only context, review-only hypotheses, and graceful degradation.
- [ ] Run focused API/Agent tests and verify expected failures.
- [ ] Implement schemas, routes, dependency wiring, prompt sections, and usage recording.
- [ ] Run focused tests and verify they pass.
- [ ] Commit the task.

### Task 7: Compatibility, documentation, and full verification

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Modify: `README.md`
- Modify: `.env.example`
- Modify: relevant compatibility tests.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: canonical dashboard composition and documented backend operation without frontend
  redesign.

- [ ] Write failing compatibility tests proving demo memory is not authoritative and canonical
  memories/ideas/reviews compose correctly.
- [ ] Implement compatibility wiring and configuration documentation.
- [ ] Run `pytest -q`, `ruff check .`, and the existing frontend suite; report every failure.
- [ ] Commit the completed backend.
