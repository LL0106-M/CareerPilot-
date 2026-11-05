# Compass Branches and Cross-Module Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicit career details from chat update a richer Compass, add company/business branches inside one direction Journey, and trigger contextual knowledge refreshes without changing the existing knowledge-library frontend.

**Architecture:** Extend the owner-scoped SQLite product projection with transactional Compass update batches, target branches, evidence/profile items, Journey branches, and contextual collection jobs. Keep the existing dashboard endpoint backward compatible by adding fields, let chat commit explicit updates only after a successful turn, and have React render the richer state in Chat, Compass, and Journey while leaving Knowledge pages untouched.

**Tech Stack:** Python 3.12, FastAPI, SQLite, Pydantic, React 19, TypeScript, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-05-compass-function-system-design.md`

## Global Constraints

- Keep the top-level flow and navigation as `对话 → 罗盘 → 航程`.
- Keep Compass direction cards as the visual center; do not turn the page into a dashboard.
- Commit explicit, quoted facts only after a successful chat turn; inferred profile/evidence items remain pending.
- One direction owns one Journey; company/business targets are branches inside it.
- A newly discovered target creates only a zero-task draft Journey branch; activation and branch-specific tasks require confirmation.
- Common Journey tasks exist once and are included dynamically in target-branch views.
- Knowledge updates asynchronously and contextually, while the existing Knowledge categories, search, cards, details, and navigation remain unchanged.
- Preserve existing APIs and records through additive fields/tables and incremental response fields.
- Do not add dependencies or redesign unrelated pages.
- Verification is intentionally focused: run the touched backend tests, the three touched page tests, TypeScript typecheck, and one production build.

## Review Focus

- A company/business-only message must attach only when the current conversation is explicitly bound to a direction; otherwise it becomes a candidate, not a new direction or formal branch.
- Repeating the same message or request must not duplicate update batches, target branches, Journey branches, tasks, or collection jobs.
- Undoing a batch must restore only projections still owned by that batch and must not delete an already-started Journey.
- Activating two target branches must reuse common tasks and keep branch-specific task state isolated.
- Contextual collection jobs for two branches in one direction must coexist without leaking results across branches or changing Knowledge navigation.

---

### Task 1: Transactional Compass update and branch projection

**Files:**
- Modify: `src/careerpilot/memory/direction_signals.py`
- Modify: `src/careerpilot/product_store.py`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `tests/memory/test_direction_signals.py`
- Modify: `tests/test_product_store.py`
- Modify: `tests/api/test_chat.py`
- Modify: `tests/api/test_directions.py`

**Interfaces:**
- Produces: `StructuredCompassItem(kind, value, explicitness, source_quote, confidence, reason)` and `DirectionSignal.items` for direction, company, business, role, location, constraint, profile, and evidence updates.
- Produces: `ProductStore.commit_compass_update(owner_id, *, run_id, conversation_id, signal) -> dict[str, object]`.
- Produces: `ProductStore.undo_compass_update(owner_id, batch_id) -> dict[str, object] | None`.
- Produces: `ProductStore.correct_compass_update_item(owner_id, batch_id, item_id, value) -> dict[str, object] | None`.
- Produces dashboard fields: `compass_update_batches`, `direction_branches`, `career_profile`, `direction_evidence`, `direction_summaries`.
- Produces: `POST /v1/me/compass-updates/{batch_id}/undo`.
- Produces: `PATCH /v1/me/compass-updates/{batch_id}/items/{item_id}` with `{ "value": ... }`.

- [ ] **Step 1: Add focused failing extraction and store tests**

  Add tests proving one quoted explicit message can extract direction/company/business/role/location/constraint/profile fields; repeated `run_id` is idempotent; an existing conversation-bound direction receives a normalized target branch; a company-only signal without a bound direction becomes a candidate; an inferred item stays pending; and correction/undo preserve later user edits.

- [ ] **Step 2: Run the focused RED tests**

  Run: `.venv\Scripts\python.exe -m pytest tests/memory/test_direction_signals.py tests/test_product_store.py tests/api/test_chat.py tests/api/test_directions.py -q`

  Expected: FAIL on missing structured fields, tables, dashboard fields, and undo endpoint.

- [ ] **Step 3: Extend `DirectionSignal` and its JSON contract**

  Keep source-quote validation. Parse a tuple of typed `StructuredCompassItem` values and require every populated explicit item to be directly supported by a substring from the current user message; downgrade unsupported values to inferred/pending instead of silently writing them.

- [ ] **Step 4: Add additive Compass tables and transactional projection methods**

  Add `compass_update_batches`, `compass_update_items`, `direction_branches`, `career_profile_items`, `direction_evidence`, and versioned `direction_summaries` tables. Store `conversation_id` on new signals/bindings, dedupe direction branches by normalized direction/company/business/role, derive reason/unknown/recent-change/next-validation summaries from stored events, and implement correction/event-based undo without deleting source messages.

- [ ] **Step 5: Commit the batch after successful chat completion and expose API fields**

  Replace the single direction write in `_save_chat_direction_signal` with `commit_compass_update`; keep the existing `direction_signal` response for compatibility and add `compass_update_batch` to `ChatResponse`.

- [ ] **Step 6: Run the focused GREEN tests**

  Run the Step 2 command.

  Expected: PASS.

### Task 2: Branched Journey lifecycle and contextual knowledge queue

**Files:**
- Modify: `src/careerpilot/product_store.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/knowledge/collection.py`
- Modify: `tests/test_product_store.py`
- Modify: `tests/api/test_journey.py`
- Modify: `tests/api/test_directions.py`
- Modify: `tests/knowledge/test_collection.py`

**Interfaces:**
- Consumes: `direction_branches.id` from Task 1.
- Produces: `ProductStore.ensure_draft_journey_branch(owner_id, direction_id, compass_branch_id) -> dict[str, object] | None`.
- Produces: `ProductStore.activate_journey_branch(owner_id, journey_id, journey_branch_id) -> dict[str, object] | None`.
- Produces dashboard field: `journey_branches` and task fields `journey_branch_id`, `scope`, `target_job_id`.
- Produces: `POST /v1/me/journeys/{journey_id}/branches/{branch_id}/activate`.
- Produces contextual collection-job fields: `compass_branch_id`, `journey_branch_id`, `normalized_query_key`, `last_verified_at`.
- Produces: `knowledge_context_links` records connecting one canonical resource to direction/Compass branch/Journey branch/target job without copying content.

- [ ] **Step 1: Add focused failing lifecycle tests**

  Add tests proving a Journey always has one common branch; a newly committed Compass target creates a zero-task draft only when the direction Journey already exists; branch activation is idempotent; common tasks are not copied; activating two targets creates separate branch-specific tasks and contextual collection jobs.

- [ ] **Step 2: Run the focused RED tests**

  Run: `.venv\Scripts\python.exe -m pytest tests/test_product_store.py tests/api/test_journey.py tests/api/test_directions.py tests/knowledge/test_collection.py -q`

  Expected: FAIL on missing Journey branches and contextual job identity.

- [ ] **Step 3: Add Journey-branch and contextual collection storage**

  Add `journey_branches` plus task scope fields. Add a new contextual collection table and `knowledge_context_links` table with unique normalized context keys, migrate/read existing direction-level jobs through the same returned contract, and leave the old table intact for compatibility.

- [ ] **Step 4: Update direction-Journey creation and branch activation**

  `start_direction_journey` creates/reuses the Journey and common branch, then creates draft target branches for existing Compass branches. `activate_journey_branch` creates only differential tasks and enqueues branch-specific job/interview/learning work.

- [ ] **Step 5: Record completed action facts as evidence**

  When `ProductStore.update_journey_task(...)` changes a task to `已完成`, append one idempotent factual evidence event tied to the direction and optional Compass branch; do not infer support/opposition automatically. When a collection result is saved, link its canonical resource ID to the same context without duplicating the resource body.

- [ ] **Step 6: Run the focused GREEN tests**

  Run the Step 2 command.

  Expected: PASS.

### Task 3: Chat right rail for this-turn updates

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/data/types.ts`
- Modify: `frontend/src/pages/chat/ChatPage.tsx`
- Modify: `frontend/src/pages/chat/ChatPage.test.tsx`
- Modify: `frontend/src/styles/pages.css`

**Interfaces:**
- Consumes: `ChatResponse.compass_update_batch`, dashboard target/Journey/collection state, and the undo endpoint from Tasks 1–2.
- Produces: a right rail with `本轮刚刚理解`, `当前关联目标`, and one context-sensitive next entry.

- [ ] **Step 1: Add one failing page test for explicit and pending updates**

  Assert that an explicit AI-product/company/business update appears as automatically saved with its source quote, an inferred priority stays pending, correction patches one item, undo calls the batch endpoint, and the next entry links to Compass rather than rendering a task or knowledge list.

- [ ] **Step 2: Run the page test RED**

  Run: `npm test -- --run src/pages/chat/ChatPage.test.tsx`

  Working directory: `frontend`

- [ ] **Step 3: Add typed contracts and replace the unused right-rail content**

  Keep Dreaming/hypothesis as a compact fallback when the current turn has no update. After a successful stream completion, show batch items, current direction/target, collection status, source quote, undo, and exactly one next link. Preserve responsive collapse behavior.

- [ ] **Step 4: Run the page test GREEN**

  Run the Step 2 command.

  Expected: PASS.

### Task 4: Richer Compass direction card and comparison

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/compass/CompassPage.tsx`
- Modify: `frontend/src/pages/compass/CompassPage.test.tsx`
- Modify: `frontend/src/styles/pages.css`

**Interfaces:**
- Consumes: dashboard `direction_branches`, `career_profile`, `direction_evidence`, `compass_update_batches`, Journey state, and collection state.
- Produces: target-branch chips/details, reason/unknown/recent-change/next-validation sections, evidence drawer, compact profile summary, and 2–3 item comparison.

- [ ] **Step 1: Add one failing Compass page test covering the complete card**

  Assert that one direction card renders two company/business branches, support/counter/unknown evidence with provenance, a recent change, a next validation point, a compact profile summary, and a fixed-dimension two-branch comparison without selecting a winner.

- [ ] **Step 2: Run the Compass page test RED**

  Run: `npm test -- --run src/pages/compass/CompassPage.test.tsx`

  Working directory: `frontend`

- [ ] **Step 3: Extend the existing direction-card layout**

  Preserve the current carousel, warm glass styling, ideas section, and Journey confirmation. Add progressive disclosure for details; show at most three focus directions on the first surface and keep other saved directions reachable without deleting them.

- [ ] **Step 4: Add client-side fixed-dimension comparison**

  Compare only directions with directions or branches under one direction. Render missing fields as `还不知道`; use stored evidence and collection facts only, with no generated match score or winner.

- [ ] **Step 5: Run the Compass page test GREEN**

  Run the Step 2 command.

  Expected: PASS.

### Task 5: Journey branch views and final focused verification

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/data/types.ts`
- Modify: `frontend/src/pages/journey/JourneyPage.tsx`
- Modify: `frontend/src/pages/journey/JourneyPage.test.tsx`
- Modify: `frontend/src/styles/pages.css`
- Verify unchanged: `frontend/src/pages/knowledge/**`

**Interfaces:**
- Consumes: dashboard `journeys`, `journey_branches`, scoped tasks, contextual collection jobs, and branch activation endpoint.
- Produces: `综合路径`, `通用主线`, and target-branch selectors inside the existing Path view.

- [ ] **Step 1: Add one failing Journey page test for draft and active branches**

  Assert that a draft target appears with `尚未开始准备`, activation requires confirmation, an active target view includes a common-foundation summary plus only its differential tasks, and calendar/footprints can filter by branch without duplicating tasks.

- [ ] **Step 2: Run the Journey page test RED**

  Run: `npm test -- --run src/pages/journey/JourneyPage.test.tsx`

  Working directory: `frontend`

- [ ] **Step 3: Add branch selectors inside the existing Journey page**

  Keep `路径 / 日历 / 足迹`, the single focus action, manual calendar creation, future letter, and external-app preview. Never create a second Journey for a target or a Journey branch per JD.

- [ ] **Step 4: Run focused frontend tests and typecheck**

  Run: `npm test -- --run src/pages/chat/ChatPage.test.tsx src/pages/compass/CompassPage.test.tsx src/pages/journey/JourneyPage.test.tsx`

  Run: `npm run typecheck`

  Working directory: `frontend`

  Expected: PASS.

- [ ] **Step 5: Run focused backend tests and production build**

  Run: `.venv\Scripts\python.exe -m pytest tests/memory/test_direction_signals.py tests/test_product_store.py tests/api/test_chat.py tests/api/test_directions.py tests/api/test_journey.py tests/knowledge/test_collection.py -q`

  Run: `npm run build`

  Working directory for build: `frontend`

  Expected: PASS. Confirm no file under `frontend/src/pages/knowledge/` changed.
