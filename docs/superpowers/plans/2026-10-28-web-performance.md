# Web Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce CareerPilot's public first-load payload and eliminate avoidable repeat downloads.

**Architecture:** Optimize visual assets at build input, add HTTP compression/cache policy at the FastAPI boundary, and split React page modules at route boundaries. Preserve the current UI and API behavior.

**Tech Stack:** React 19, Vite 7, FastAPI/Starlette, Vitest, pytest, ffmpeg WebP encoder

**Spec:** `docs/superpowers/specs/2026-10-28-web-performance-design.md`

## Global Constraints

- Keep the existing visual composition and routes.
- HTML must remain revalidated; only versioned/hash-named assets are immutable.
- Do not introduce a new runtime dependency for image delivery.

## Review Focus

- Guests must not download authenticated page modules before authentication resolves.
- SPA fallback HTML must never receive immutable caching.
- API JSON must remain valid when gzip is requested.
- Transparent character and wordmark assets must retain transparency.
- Route chunks must still render under Suspense in tests and production.

---

### Task 1: Optimized visual assets

**Files:**
- Create: `frontend/public/assets/*-v1.webp`
- Modify: frontend asset references
- Test: `frontend/src/app/assets-performance.test.ts`

**Interfaces:**
- Consumes: Existing PNG visual sources.
- Produces: Versioned WebP assets under a combined 1 MB budget.

- [ ] Write the asset budget test and confirm it fails because WebP files are absent.
- [ ] Encode resized WebP assets and update source references.
- [ ] Run the focused test and confirm it passes.

### Task 2: HTTP compression and caching

**Files:**
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/api/static.py`
- Test: `tests/api/test_static_app.py`

**Interfaces:**
- Consumes: Static and API responses.
- Produces: gzip for responses over 500 bytes; immutable caching for `/assets/`; `no-cache` for HTML.

- [ ] Add failing response-header tests.
- [ ] Add gzip middleware and static cache policy.
- [ ] Run focused backend tests and confirm they pass.

### Task 3: Route-level code splitting

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/App.lazy.test.tsx`

**Interfaces:**
- Consumes: Existing named page exports.
- Produces: Lazy page components rendered beneath one Suspense boundary.

- [ ] Add a failing test proving `/login` eagerly loads `TodayPage`.
- [ ] Replace eager page imports with named-export lazy loaders.
- [ ] Run focused frontend tests and confirm they pass.

### Task 4: Production verification

**Files:**
- Verify all modified files and generated build output.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: A verified production bundle and public deployment measurement.

- [ ] Run full frontend and backend suites, lint, and production build.
- [ ] Rebuild/restart the local deployment behind ngrok.
- [ ] Measure local and public headers, payload sizes, and response times.
