# Click-to-Dreaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a signed-in user click to generate and persist one refreshable Dreaming result per day from their most recent seven days of data.

**Architecture:** Extend the existing SQLite cognitive store with owner-scoped manual generation jobs and persisted daily output. A focused service aggregates seven-day evidence, runs the existing Dreaming analyzer in a background task, and updates the durable job/result state. The React page starts generation, polls status, renders real output, and confirms selected hypotheses into canonical memory for Compass.

**Tech Stack:** FastAPI, asyncio, SQLite, Pydantic, React, TypeScript, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-click-to-dreaming-design.md`

## Global Constraints

- Data window is exactly the signed-in user's most recent 7 calendar days.
- `(owner_id, local_date)` identifies the single daily Dreaming result; regeneration updates it and increments its version.
- A failed regeneration must retain the previous successful result.
- Generated directions remain candidates until the user explicitly confirms one into Compass.
- No scheduled or hidden-keyword trigger is added by this feature.

## Review Focus

- Double-click/concurrent regenerate requests return the same active job rather than running twice.
- A user with no eligible evidence receives an actionable empty-data response and no fabricated result.
- A model or network failure transitions the job to failed while preserving the prior published result.
- All job, result, and confirmation lookups reject cross-owner access.
- Page reload during generation resumes polling the persisted active job.

---

### Task 1: Durable Daily Dreaming State

**Files:**
- Modify: `src/careerpilot/memory/cognitive_store.py`
- Modify: `src/careerpilot/memory/dreaming.py`
- Test: `tests/memory/test_dreaming.py`

**Interfaces:**
- Produces: `ManualDreamingJob`, `DailyDreamingResult`, `start_manual_job(owner_id, local_date, evidence_json)`, `get_manual_job(owner_id, job_id)`, `complete_manual_job(...)`, and `fail_manual_job(...)`.

- [ ] Write failing store tests for one daily result, same-active-job reuse, successful overwrite/version increment, failure preservation, and owner isolation.
- [ ] Run `pytest tests/memory/test_dreaming.py -q` and verify the new tests fail for missing interfaces.
- [ ] Add the manual job/result schema and typed store methods, using transactions and the `(owner_id, local_date)` uniqueness rule.
- [ ] Run `pytest tests/memory/test_dreaming.py -q` and verify all tests pass.

### Task 2: Seven-Day Evidence and Generation Service

**Files:**
- Create: `src/careerpilot/memory/manual_dreaming.py`
- Test: `tests/memory/test_manual_dreaming.py`

**Interfaces:**
- Consumes: Task 1 store interfaces, `MemoryService`, `ProductStore`, and `RagStore` read APIs.
- Produces: `ManualDreamingService.start(owner_id: str, local_date: date)`, `run(job_id: str)`, `status(owner_id: str, job_id: str)`, and `confirm_hypothesis(owner_id: str, result_id: str, hypothesis_index: int)`.

- [ ] Write failing service tests proving seven-day filtering, inclusion of conversations/ideas/hypotheses/documents, empty-evidence rejection, analyzer completion, failure state, and explicit confirmation.
- [ ] Run `pytest tests/memory/test_manual_dreaming.py -q` and verify expected failures.
- [ ] Implement the minimal aggregation and generation service using the existing JSON Dreaming analyzer and canonical hypothesis memory creation.
- [ ] Run `pytest tests/memory/test_manual_dreaming.py -q` and verify all tests pass.

### Task 3: Authenticated Dreaming API

**Files:**
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/api/schemas.py`
- Create: `tests/api/test_manual_dreaming.py`

**Interfaces:**
- Consumes: `ManualDreamingService` from Task 2.
- Produces: `POST /v1/me/dreaming`, `GET /v1/me/dreaming/today`, `GET /v1/me/dreaming/jobs/{job_id}`, and `POST /v1/me/dreaming/results/{result_id}/hypotheses/{index}/confirm`.

- [ ] Write failing authenticated API tests for start, active-job reuse, today/status reads, empty evidence, confirmation, and cross-owner denial.
- [ ] Run `pytest tests/api/test_manual_dreaming.py -q` and verify expected failures.
- [ ] Wire the service into app construction, run generation in an application background task, and add owner-scoped schemas/routes.
- [ ] Run `pytest tests/api/test_manual_dreaming.py -q` and verify all tests pass.

### Task 4: Real Dreaming Page

**Files:**
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/dreaming/DreamingPage.tsx`
- Modify: `frontend/src/styles/pages.css`
- Create: `frontend/src/pages/dreaming/DreamingPage.test.tsx`

**Interfaces:**
- Consumes: Task 3 endpoints.
- Produces: typed Dreaming client methods and a page with start/regenerate, durable polling, real result cards, failure/empty states, and confirm-to-Compass actions.

- [ ] Write failing component tests for initial empty state, generation/polling, reload resume, completed rendering, same-day update wording, failure retry, and confirmation success.
- [ ] Run `npm test -- --run src/pages/dreaming/DreamingPage.test.tsx` and verify expected failures.
- [ ] Add typed API methods and replace `demoDreams` with the real stateful page; keep polling bounded and cancel it on unmount.
- [ ] Add responsive styles and accessible live status/button labels.
- [ ] Run `npm test -- --run src/pages/dreaming/DreamingPage.test.tsx` and verify all tests pass.

### Task 5: Integration, Build, and Live Update

**Files:**
- Modify only if required by verification failures.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: verified production build served by the existing FastAPI/ngrok deployment.

- [ ] Run `pytest -q` and report zero failures.
- [ ] Run `npm test -- --run` in `frontend` and report zero failures.
- [ ] Run `npm run build` in `frontend` and verify the production bundle succeeds.
- [ ] Restart the local FastAPI service if required so it loads the new routes and bundle.
- [ ] Verify health, authenticated route behavior, Dreaming start/status/result flow, and the unchanged ngrok URL.
