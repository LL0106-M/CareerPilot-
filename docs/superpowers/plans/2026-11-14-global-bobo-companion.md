# Global Bobo Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an animated, route-aware Bobo to every protected product page with a shared side conversation that hands off to full chat and uses the existing governed memory pipeline.

**Architecture:** A new `CompanionBobo` feature is mounted once by `AppShell` and derives presentation plus bounded context from the current route. It persists only the active conversation ID, calls the existing streaming chat API with validated `page_context`, and hands that ID to `ChatPage`; backend page context augments the system prompt but never the stored user message.

**Tech Stack:** React 19, React Router, Framer Motion, Vitest/Testing Library, FastAPI/Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-global-bobo-companion-design.md`

## Global Constraints

- Reuse `/v1/chat/stream`; no second chat or memory store.
- Preserve existing CareerPilot colors, Bobo asset, and governed memory write policy.
- Never silently send a message or write page metadata into conversation history.
- Hide the global dock on `/chat`; full chat is the same Bobo in expanded form.
- Respect `prefers-reduced-motion`.

## Review Focus

- A stored companion conversation that no longer exists must fall back to a new conversation without trapping the drawer.
- Route changes while the drawer is open must update page context without losing messages.
- Failed streaming responses must restore the user's draft and remove the empty agent bubble.
- The `/chat` route must not render a duplicate global dock.
- Page context must be rejected when it contains unknown fields or oversized values.

---

### Task 1: Page-aware Bobo presentation

**Files:**
- Create: `frontend/src/components/bobo/companionConfig.ts`
- Create: `frontend/src/components/bobo/CompanionBobo.tsx`
- Create: `frontend/src/components/bobo/companion-bobo.css`
- Test: `frontend/src/components/bobo/CompanionBobo.test.tsx`
- Modify: `frontend/src/components/bobo/Bobo.tsx`
- Modify: `frontend/src/components/layout/AppShell.tsx`

**Interfaces:**
- Produces: `getCompanionConfig(pathname: string): CompanionConfig` and `CompanionBobo`.
- Consumes: existing `Bobo` mood animation and design tokens.

- [ ] Write tests that each core route maps to a distinct mood/prompt/accent and `/chat` suppresses the dock.
- [ ] Run `npm test -- src/components/bobo/CompanionBobo.test.tsx` and verify RED because the component/config do not exist.
- [ ] Implement the route configuration, dock, drawer shell, Escape handling, and route-specific motion classes.
- [ ] Mount `CompanionBobo` in `AppShell`.
- [ ] Run the focused test and verify GREEN.

### Task 2: Shared sidebar conversation and full-chat handoff

**Files:**
- Create: `frontend/src/components/bobo/companionSession.ts`
- Modify: `frontend/src/components/bobo/CompanionBobo.tsx`
- Modify: `frontend/src/components/bobo/CompanionBobo.test.tsx`
- Modify: `frontend/src/pages/chat/ChatPage.tsx`
- Modify: `frontend/src/pages/chat/ChatPage.test.tsx`
- Modify: `frontend/src/app/App.tsx`

**Interfaces:**
- Produces: persisted `careerpilot.companionConversationId`, drawer streaming behavior, and full-chat route-state handoff.
- Consumes: `api.chatStream`, `api.getConversation`, `MessageContent`, and `getCompanionConfig`.

- [ ] Write failing tests for sending in the drawer, retaining `conversation_id`, opening the same conversation in `/chat`, failure recovery, and no duplicate dock on chat.
- [ ] Run focused frontend tests and verify RED.
- [ ] Implement shared session persistence, drawer messages/composer, handoff state, and add the existing `MemoryPage` route.
- [ ] Run focused frontend tests and verify GREEN.

### Task 3: Bounded backend page context

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/data/api.test.ts`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/agent/service.py`
- Modify: `tests/api/test_chat.py`
- Modify: `tests/agent/test_service.py`

**Interfaces:**
- Produces: optional `ChatRequest.page_context` and `ChatCommand.page_context`, system-prompt-only context injection.
- Consumes: the existing chat streaming, history persistence, memory lifecycle, and direction detector.

- [ ] Write failing API tests proving valid context reaches `ChatCommand`, invalid extra fields return 422, and stored history contains only the raw user message.
- [ ] Write a failing service test proving page context appears in system context while memory commit and direction detection receive the raw message.
- [ ] Run focused pytest targets and verify RED.
- [ ] Implement validated schema, command propagation, and escaped system-context formatting.
- [ ] Update the frontend request contract and API serialization test.
- [ ] Run focused frontend and backend tests and verify GREEN.

### Task 4: Verification and visual integration

**Files:**
- Modify as required by failures only.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified build and regression-safe feature.

- [ ] Run `npm test` in `frontend` and record all results.
- [ ] Run `npm run build` in `frontend` and verify exit 0.
- [ ] Run `pytest` and record all results.
- [ ] Inspect the feature in the local browser at desktop and mobile widths; fix only issues covered by a failing test first.
