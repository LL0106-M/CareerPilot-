# CareerPilot Unified Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved five-page CareerPilot MVP as a dynamic, warm-frosted React experience backed by the existing FastAPI product APIs, with clear cross-page handoffs and confirmation boundaries.

**Architecture:** A typed `apiClient` is the only browser-to-server boundary. Page hooks load server state and surface loading, empty, offline, and retry states. The router carries only navigational context (`state` and query params); durable state is always reloaded from FastAPI. Shared ambient motion and frosted components live below `AppShell`, while each page owns its task-specific interactions.

**Tech Stack:** React 19, React Router 7, TypeScript, Framer Motion, Phosphor Icons, Vite/Vitest, FastAPI, SQLite.

**Spec:** `docs/superpowers/specs/2026-10-25-careerpilot-homepage-hero-design.md`, `docs/superpowers/specs/2026-10-25-careerpilot-chat-page-design.md`, `docs/superpowers/specs/2026-10-25-careerpilot-compass-page-design.md`, `docs/superpowers/specs/2026-10-25-careerpilot-journey-page-design.md`, `docs/superpowers/specs/2026-10-25-careerpilot-knowledge-library-page-design.md`

## Global Constraints

- Preserve existing backend owner isolation and HttpOnly-cookie identity; never send `user_id` from the browser.
- Dreaming may be stored automatically. Compass, Journey, Knowledge, and external-app mutations require explicit user confirmation.
- Use real API data when available; curated learning resources may ship as editorial seed content, but fake jobs and fake personal documents must not be shown as user data.
- Reuse the supplied CareerPilot landscape, wordmark, and Bobo assets. Do not imitate reference-site brands or imagery.
- Motion must respond to pointer/scroll, remain subtle, and honor `prefers-reduced-motion`.
- Mobile and desktop layouts must remain usable without forcing a fixed 1100px canvas.

## Review Focus

- Cross-page navigation preserves intent without treating router state as durable data.
- Failed or empty API responses never silently substitute fake personal data.
- Chat uses automatic support-mode selection and does not expose manual mode controls.
- Every mutation communicates pending/success/error and respects confirmation rules.
- Glass surfaces remain individually layered; the entire page is not one shared frosted panel.
- Pointer, scroll, keyboard, responsive, and reduced-motion behavior are all verified.

---

## Task 1: Typed API boundary and shared async states

**Files:**
- Create: `frontend/src/data/api.ts`
- Create: `frontend/src/data/api.test.ts`
- Create: `frontend/src/hooks/useDashboard.ts`
- Modify: `frontend/vite.config.ts`

- [ ] Write failing tests for cookie-aware JSON requests, normalized API errors, dashboard loading, chat request payloads, idea creation, job/document loading, hypothesis decisions, and journey updates.
- [ ] Run `npm test -- --run src/data/api.test.ts` from `frontend`; expect failure because the client does not exist.
- [ ] Implement typed request/response contracts and `credentials: 'include'`; configure `/v1` and `/health` development proxy to the FastAPI server.
- [ ] Re-run the focused test and `npm run typecheck`; expect both to pass.
- [ ] Commit only Task 1 files with message `feat(frontend): add typed CareerPilot API client`.

## Task 2: Shared shell, ambient scene, and responsive navigation

**Files:**
- Create: `frontend/src/components/ambient/AmbientScene.tsx`
- Create: `frontend/src/components/ambient/ambient-scene.css`
- Modify: `frontend/src/components/layout/AppShell.tsx`
- Modify: `frontend/src/components/layout/app-shell.css`
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/global.css`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/App.test.tsx`

- [ ] Update tests first for the five approved navigation items, `/` home route, active navigation, and absence of primary `记忆` navigation.
- [ ] Run `npm test -- --run src/app/App.test.tsx`; expect old navigation assertions to fail.
- [ ] Implement the centered frosted capsule nav, mobile overflow behavior, animated landscape layers, pointer parallax, and reduced-motion fallback.
- [ ] Re-run the focused test and typecheck.
- [ ] Commit Task 2 files with message `feat(frontend): unify shell and ambient motion`.

## Task 3: Dynamic homepage and real chat handoff

**Files:**
- Modify: `frontend/src/pages/today/TodayPage.tsx`
- Modify: `frontend/src/pages/chat/ChatPage.tsx`
- Create: `frontend/src/pages/today/HomePage.test.tsx`
- Create: `frontend/src/pages/chat/ChatPage.test.tsx`
- Modify: `frontend/src/styles/pages.css`

- [ ] Write failing interaction tests for homepage chat handoff, explicit quick-idea save, mouse-responsive Bobo scene, Dreaming section, footer columns, chat request/response, left history collapse, right context drawer, and backend error retry.
- [ ] Run the two focused test files; expect failures against the static pages.
- [ ] Build the scrollable homepage: English companion headline, short helper copy, embedded chat entry, separate quick-thought composer, interactive Bobo, Dreaming orbital section, and English product footer.
- [ ] Build the dedicated chat workspace: collapsible local conversation history/folders, automatic-mode conversation, attachment affordance, dynamic background, and right context drawer. Call `POST /v1/chat`; navigate from homepage with draft text and submit only after the user sends.
- [ ] Call `POST /v1/me/ideas` only after the homepage quick-thought user explicitly presses save; show pending/success/error feedback.
- [ ] Run focused tests, the frontend suite, and typecheck.
- [ ] Commit Task 3 files with message `feat(frontend): build companion home and connected chat`.

## Task 4: Connected Compass and Journey views

**Files:**
- Modify: `frontend/src/pages/compass/CompassPage.tsx`
- Modify: `frontend/src/pages/journey/JourneyPage.tsx`
- Create: `frontend/src/pages/compass/CompassPage.test.tsx`
- Create: `frontend/src/pages/journey/JourneyPage.test.tsx`
- Modify: `frontend/src/styles/pages.css`

- [ ] Write failing tests for dashboard rendering, one-direction-at-a-time exploration, confirmed hypothesis decisions, idea-wall presentation, multi-journey switching, path/calendar/footprint views, task progress updates, and external action preview confirmation.
- [ ] Run focused tests; expect failures against demo-only pages.
- [ ] Rebuild Compass as two scroll chapters: focused direction exploration followed by a scattered idea wall. Load `/v1/me/dashboard`; mutation buttons call hypothesis endpoints only after explicit action.
- [ ] Rebuild Journey with Path as default and Calendar/Footprints as secondary views. Support multiple journey groupings, one visible focus action per group, milestones, and task state mutation via `/v1/me/journey/{task_id}`.
- [ ] Add external-app action preview UI using `/v1/me/actions/preview`; do not apply until the existing confirmation/apply sequence is completed.
- [ ] Run focused tests, full frontend suite, and typecheck.
- [ ] Commit Task 4 files with message `feat(frontend): connect compass and journey workflows`.

## Task 5: Finite knowledge dashboard with real data

**Files:**
- Modify: `frontend/src/pages/knowledge/KnowledgeLayout.tsx`
- Modify: `frontend/src/pages/knowledge/jobs/JobsPage.tsx`
- Modify: `frontend/src/pages/knowledge/preparation/PreparationPage.tsx`
- Modify: `frontend/src/pages/knowledge/personal/PersonalPage.tsx`
- Modify: `frontend/src/pages/knowledge/knowledge-pages.test.tsx`
- Create: `frontend/src/data/curatedLearning.ts`
- Modify: `frontend/src/styles/pages.css`

- [ ] Rewrite tests first for the three in-page library tabs, featured selection priority, API-loaded jobs/documents, filters, source links, editorial AI collections, and the absence of fabricated personal/job rows on empty responses.
- [ ] Run focused knowledge tests; expect failures.
- [ ] Build the finite library dashboard patterned after the supplied archive reference: compact recent rail, one featured record, and horizontally scrollable shelves. Keep three route-compatible tabs for personal, jobs, and learning.
- [ ] Load jobs from `/v1/knowledge/jobs`, preparation metadata from `/v1/knowledge/preparation`, and documents from `/v1/me/documents`. Use curated verified learning links as editorial content only.
- [ ] Keep natural-language web collection in Chat via a clear cross-page prompt action; retain page-level keyword/filter controls.
- [ ] Run focused tests, full frontend suite, and typecheck.
- [ ] Commit Task 5 files with message `feat(frontend): build connected knowledge library`.

## Task 6: End-to-end integration and visual QA

**Files:**
- Modify as required by verified defects only.
- Create: `frontend/src/app/cross-page-flow.test.tsx`

- [ ] Write a cross-page test for Home draft → Chat reply → Compass context link → Journey task → Knowledge resource link.
- [ ] Run the cross-page test and make only the minimal integration changes needed to pass.
- [ ] Run `npm test`, `npm run typecheck`, and `npm run build` in `frontend`.
- [ ] Run relevant backend API tests for chat, dashboard, product store, and knowledge endpoints.
- [ ] Start the local frontend and backend; inspect all five pages in the in-app browser at desktop and narrow widths, test pointer/scroll/tabs/forms, inspect console errors, and compare against the supplied visual references.
- [ ] Run a fresh whole-branch review focused on the Review Focus section; fix Critical/Important findings with RED→GREEN tests.
- [ ] Commit verified integration fixes with message `test(frontend): verify unified CareerPilot experience`.
