# Agent Memory Direction Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the direct technical handbook and ship the first end-to-end Agent Memory vertical slice: LLM direction signals returned by chat and user-controlled promotion into Compass.

**Architecture:** Keep the authoritative unified memory store, add a separate structured direction-signal detector, and expose its result through the chat contract. Explicit signals become confirmed domain directions; implicit signals remain prompts until the user accepts them. The frontend renders returned state and never invents a company or role.

**Tech Stack:** Python 3.12, FastAPI, SQLite, LangChain chat models, pytest, React, TypeScript, Vitest.

**Spec:** `docs/architecture/agent-memory-handbook.md`

## Global Constraints

- Preserve unrelated dirty-worktree changes.
- Do not hard-code any company, role, direction, journey, or task.
- LLM output is validated data, never a direct database write.
- Joining Compass never creates a Journey.
- No standalone memory-management page.
- Every production behavior change follows RED -> GREEN TDD.

## Review Focus

- Malformed or unavailable LLM output degrades to `none` without breaking chat.
- An implicit direction cannot become active before a user acceptance request.
- An explicit direction is owner-scoped and idempotent for the source run.
- A stale implicit prompt cannot add another user's direction.
- Existing chat clients remain compatible when no direction signal is returned.

---

### Task 1: Technical handbook

**Files:**
- Create: `docs/architecture/agent-memory-handbook.md`

**Interfaces:**
- Produces: binding boundaries, memory classes, write/read protocols, and direction-signal contract.

- [x] Write the concise engineering handbook.
- [x] Verify the implementation plan uses the same names and boundaries.

### Task 2: Direction signal detector

**Files:**
- Create: `src/careerpilot/memory/direction_signals.py`
- Create: `tests/memory/test_direction_signals.py`
- Modify: `src/careerpilot/agent/service.py`
- Modify: `src/careerpilot/api/dependencies.py`

**Interfaces:**
- Produces: `DirectionSignal`, `DirectionExplicitness`, `DirectionSignalDetector.analyze(user_message, assistant_message)`.
- Consumes: a reasoning chat model with `ainvoke`.

- [x] Write failing tests for valid explicit/implicit JSON, malformed output, and no-signal output.
- [x] Run focused tests and verify RED.
- [x] Implement strict JSON parsing and safe fallback.
- [x] Inject the detector and add the signal to successful `ChatResult` values.
- [x] Run focused tests and verify GREEN.

### Task 3: Owner-scoped direction state and API

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `tests/api/test_chat.py`
- Create: `tests/api/test_directions.py`

**Interfaces:**
- Consumes: `DirectionSignal` from Task 2.
- Produces: chat `direction_signal`, owner-scoped directions, and `POST /v1/me/direction-signals/{signal_id}/accept`.

- [x] Write failing API/store tests for explicit auto-confirm, implicit pending, accept, idempotency, and owner isolation.
- [x] Run focused tests and verify RED.
- [x] Add direction tables and domain methods without creating Journey tasks.
- [x] Persist completed-chat signals and expose them in dashboard/chat responses.
- [x] Run focused tests and verify GREEN.

### Task 4: Dynamic chat prompt and Compass projection

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/chat/ChatPage.tsx`
- Modify: `frontend/src/pages/chat/ChatPage.test.tsx`
- Modify: `frontend/src/pages/compass/CompassPage.tsx`
- Modify: `frontend/src/pages/compass/CompassPage.test.tsx`

**Interfaces:**
- Consumes: chat `direction_signal`, accept endpoint, dashboard directions.
- Produces: inline implicit confirmation and dynamic Compass direction rendering.

- [x] Write failing UI tests for implicit prompt, accept, explicit acknowledgement, and absence when signal is `none`.
- [x] Run focused tests and verify RED.
- [x] Add typed API contracts and inline controls.
- [x] Replace idea-to-Journey action with direction exploration while retaining scattered cards.
- [x] Run focused tests, typecheck, and build; verify GREEN.

### Task 5: Integrated verification

**Files:**
- Modify tests only after adding a failing regression test for any discovered bug.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: a verified event-to-signal-to-Compass vertical slice.

- [x] Run focused Python memory, agent, API, and product-store tests.
- [x] Run focused frontend chat and Compass tests.
- [x] Run full Python and frontend suites and production build.
- [x] Inspect for hard-coded direction data and stale idea-to-Journey actions.
