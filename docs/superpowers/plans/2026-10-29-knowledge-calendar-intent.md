# Knowledge Refresh, Intent, and Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix knowledge refresh and calendar intent, then ship a first-party CareerPilot calendar with chat/manual creation, reminders, Tencent Meeting links, and optional Feishu sync.

**Architecture:** Extend the owner-scoped product store and dashboard contract for local events. Use a conservative deterministic chat parser at the API boundary and keep external calendar sync behind the existing preview/confirm flow. Make knowledge persistence and page refresh behavior match the UI promise.

**Tech Stack:** FastAPI, Pydantic, SQLite, React, TypeScript, Vitest, pytest

**Spec:** `docs/superpowers/specs/2026-10-29-knowledge-calendar-intent-design.md`

## Global Constraints

- Preserve all unrelated dirty-worktree changes.
- Tencent Meeting support is an attached HTTPS URL, not direct meeting creation.
- Local storage succeeds independently of Feishu availability.
- Chat writes require explicit schedule/reminder language.

## Review Focus

- Ambiguous date phrases must not silently create the wrong event.
- Invalid or non-HTTPS meeting links must be rejected.
- Event reads and writes must stay owner-scoped.
- Existing verification tasks without new fields must still render.
- Knowledge pages must distinguish saved records from transient search results.

---

### Task 1: Calendar intent and chat extraction

**Files:**
- Modify: `src/careerpilot/context/contracts.py`
- Modify: `src/careerpilot/context/intent.py`
- Create: `src/careerpilot/journey/chat_parser.py`
- Test: `tests/context/test_intent.py`
- Test: `tests/journey/test_chat_parser.py`

**Interfaces:**
- Produces: `TaskIntent.CALENDAR_MANAGEMENT` and `parse_calendar_request(message, now) -> ParsedCalendarRequest | None`.

- [ ] Write tests for reminder/event phrases, extracted Tencent URL, and non-action false positives.
- [ ] Run focused tests and verify they fail for the missing intent/parser.
- [ ] Add the intent markers and minimal conservative parser.
- [ ] Run focused tests and verify they pass.

### Task 2: Owner-scoped local calendar API

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/app.py`
- Test: `tests/test_product_store.py`
- Test: `tests/api/test_memory_dashboard.py`
- Create: `tests/api/test_journey.py`

**Interfaces:**
- Consumes: `ParsedCalendarRequest` from Task 1.
- Produces: `ProductStore.create_journey_event(...)` and `POST /v1/me/journey`.

- [ ] Write failing migration, validation, owner-isolation, manual-create, and chat-create tests.
- [ ] Run focused tests and verify expected failures.
- [ ] Add backward-compatible columns, create method, request schema, endpoint, and chat-boundary creation.
- [ ] Run focused tests and verify they pass.

### Task 3: First-party calendar and reminders UI

**Files:**
- Modify: `frontend/src/data/types.ts`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/journey/JourneyPage.tsx`
- Modify: `frontend/src/styles/pages.css`
- Test: `frontend/src/pages/journey/JourneyPage.test.tsx`

**Interfaces:**
- Consumes: `POST /v1/me/journey` and enriched dashboard journey records.
- Produces: manual event dialog, calendar event cards, reminder scheduling, Tencent Meeting links, optional Feishu sync.

- [ ] Write failing tests for manual add, reminder fields, and Tencent link rendering.
- [ ] Run focused tests and verify expected failures.
- [ ] Add typed API client, form, local notification scheduling, and event rendering.
- [ ] Run focused tests and verify they pass.

### Task 4: Knowledge save and refresh truthfulness

**Files:**
- Modify: `src/careerpilot/rag/tool.py`
- Modify: `src/careerpilot/agent/prompt.py`
- Modify: `frontend/src/pages/knowledge/jobs/JobsPage.tsx`
- Modify: `frontend/src/pages/knowledge/preparation/PreparationPage.tsx`
- Test: `tests/rag/test_agentic_tool.py`
- Test: `frontend/src/pages/knowledge/knowledge-pages.test.tsx`

**Interfaces:**
- Produces: consistent `save_to_library` behavior and explicit page refresh/updated state.

- [ ] Write failing tests for job-scope saving and UI refresh.
- [ ] Run focused tests and verify expected failures.
- [ ] Persist honest job-source records, update tool/prompt copy, and add page refresh indicators.
- [ ] Run focused tests and verify they pass.

### Task 5: Verification

**Files:**
- Modify only files needed for failures caused by Tasks 1-4.

- [ ] Run all backend tests.
- [ ] Run all frontend tests and production build.
- [ ] Review the final diff for unrelated changes and report any pre-existing failures.
