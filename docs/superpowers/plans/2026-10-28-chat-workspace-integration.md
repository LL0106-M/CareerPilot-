# Chat Workspace Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the chat workspace to durable owner data and deliver real model text incrementally.

**Architecture:** Add an SSE adapter around the existing harness stream while retaining the JSON endpoint. Extend the typed frontend client for conversations and streaming, then make `ChatPage` consume conversations and dashboard context directly.

**Tech Stack:** FastAPI, Python async generators, React, TypeScript, native Fetch streams, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-28-chat-workspace-integration-design.md`

## Global Constraints

- Preserve `/v1/chat` JSON compatibility.
- Add no frontend dependency.
- Persist only completed turns and keep all conversation reads owner-scoped.
- Preserve existing responsive side-panel behavior and styling.

## Review Focus

- Fragmented SSE frames must parse without dropping or duplicating text.
- A failed stream must remove/replace the in-progress placeholder and surface an error.
- Selecting a conversation while another turn is sending must not corrupt message state.
- Empty conversation/dashboard responses must show honest empty states.
- Cross-site cookie mutations remain rejected while proxied same-origin requests pass.

---

### Task 1: Reverse-proxy same-origin protection

**Files:**
- Modify: `src/careerpilot/api/app.py`
- Test: `tests/api/test_auth.py`

**Interfaces:**
- Produces: same-origin predicate used by cookie-mutation middleware.

- [ ] Add failing tests for an ngrok-style forwarded same-origin POST and a foreign Origin POST.
- [ ] Run the focused tests and confirm the forwarded request fails before implementation.
- [ ] Implement effective origin comparison using configured origins plus forwarded protocol/host.
- [ ] Run the focused tests and confirm both security cases pass.

### Task 2: Agent and API streaming contract

**Files:**
- Modify: `src/careerpilot/agent/service.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/api/schemas.py`
- Test: `tests/agent/test_service.py`
- Test: `tests/api/test_chat.py`

**Interfaces:**
- Produces: `AgentService.stream_chat(command)` events and `POST /v1/chat/stream` SSE events named `delta`, `completed`, and `error`.

- [ ] Add failing service and API tests proving early deltas, final metadata, and completed-turn persistence.
- [ ] Run focused tests and confirm missing streaming behavior is the failure.
- [ ] Implement the service stream and make the JSON method collect its completion result.
- [ ] Implement the SSE endpoint with disconnect-aware event serialization.
- [ ] Run focused tests and confirm both legacy JSON and streaming contracts pass.

### Task 3: Typed frontend data and SSE parser

**Files:**
- Modify: `frontend/src/data/api.ts`
- Test: `frontend/src/data/api.test.ts`

**Interfaces:**
- Produces: `ConversationSummary`, `ConversationDetail`, `getConversations()`, `getConversation(id)`, and `chatStream(body, onDelta)`.

- [ ] Add failing tests for fragmented SSE parsing, final response return, and conversation requests.
- [ ] Run the focused test and confirm the new methods are absent.
- [ ] Implement the minimal typed client and parser with buffered frame handling.
- [ ] Run the focused test and confirm it passes.

### Task 4: Live chat workspace

**Files:**
- Modify: `frontend/src/pages/chat/ChatPage.tsx`
- Modify: `frontend/src/pages/chat/ChatPage.test.tsx`
- Modify: `frontend/src/styles/pages.css` only if an empty/loading state needs existing spacing utilities extended.

**Interfaces:**
- Consumes: Task 3 API methods and existing `getDashboard()`.

- [ ] Add failing UI tests for loaded conversation titles, reopening messages, streamed deltas, refresh after completion, dashboard-derived context, and empty states.
- [ ] Run the focused test and confirm hard-coded content/missing methods cause failure.
- [ ] Replace static rails and JSON send behavior with live state while preserving panel toggles and attachments.
- [ ] Run the focused test and confirm it passes.
- [ ] Run frontend test suite/build and backend test suite; report every failure.
