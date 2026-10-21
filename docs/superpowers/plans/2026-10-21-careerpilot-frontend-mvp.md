# CareerPilot Frontend MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deployable desktop-first CareerPilot React application with a dynamic 泊泊 companion, preserved Dreaming experience, functional navigation, chat API integration, and concrete knowledge-base pages for jobs, preparation materials, and personal uploads.

**Architecture:** Add an isolated `frontend/` Vite React TypeScript SPA. Page components consume typed repository interfaces; the chat repository calls the existing `/v1/chat`, while business APIs that do not yet exist use an explicitly marked demo repository so UI work is not coupled to fake backend contracts. Shared glass components, tokens, routes, and mascot state live in focused modules.

**Tech Stack:** React 19, TypeScript, Vite, React Router, Framer Motion, Lucide React, Vitest, Testing Library, plain CSS design tokens.

**Spec:** `frontend-design-spec.md`

## Global Constraints

- Desktop Web is the delivery target; no mobile screens in this iteration.
- Preserve CareerPilot's handcrafted wordmark, forest/mint/sky/amber palette, and warm glassmorphism.
- Dreaming remains a first-class route and Today-page summary.
- 泊泊 visibly reacts to `idle`, `listen`, `organize`, `explore`, `act`, `thinking`, and `dreaming` states.
- Knowledge base is separate from personal memory.
- Jobs use a filterable data table with enterprise type, enterprise, role, role type, deadline, and expired status.
- Preparation materials use interview/笔试 primary tabs and the specified secondary categories.
- Personal materials are user-uploaded resume, projects/portfolio, and other documents.
- Missing backend endpoints must be represented by a replaceable demo repository and never presented as persisted production data.
- The app must build as static assets and accept `VITE_API_BASE_URL` at deployment time.

## Review Focus

- API outage or missing configuration must leave the user with a clear retryable error, not a blank page.
- Filters with no results must render a useful empty state and retain the active filter criteria.
- Long enterprise, role, and file names must truncate without breaking the table or hiding actions.
- Reduced-motion users must not receive looping mascot motion.
- Knowledge citations and private-document labels must remain visibly distinct from long-term memory.

---

### Task 1: Frontend Foundation And App Shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/App.test.tsx`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/global.css`
- Create: `frontend/src/components/layout/AppShell.tsx`

**Interfaces:**
- Produces: an app shell with routes and top navigation slots consumed by all page tasks.

- [ ] Write a failing test that expects the CareerPilot brand and all seven top-level navigation labels.
- [ ] Run the test and verify it fails because the app does not exist.
- [ ] Implement the Vite foundation, global tokens, and glass top navigation.
- [ ] Run the test and verify it passes.

### Task 2: Dynamic Bobo State Component

**Files:**
- Create: `frontend/src/components/bobo/Bobo.tsx`
- Create: `frontend/src/components/bobo/Bobo.test.tsx`
- Create: `frontend/src/components/bobo/bobo.css`
- Create: `frontend/src/assets/` or `frontend/public/assets/` production image assets.

**Interfaces:**
- Produces: `Bobo({ mood, size, label })` and `BoboMood` for Today, Chat, and Dreaming.
- Consumes: visual tokens from Task 1.

- [ ] Write failing tests for accessible mood labels and status-class mapping.
- [ ] Verify the tests fail before implementation.
- [ ] Implement image-based mascot states with restrained motion and reduced-motion support.
- [ ] Verify component tests pass.

### Task 3: Typed Demo Repositories And Knowledge Filters

**Files:**
- Create: `frontend/src/data/types.ts`
- Create: `frontend/src/data/demoRepository.ts`
- Create: `frontend/src/data/filtering.ts`
- Create: `frontend/src/data/filtering.test.ts`

**Interfaces:**
- Produces: typed jobs, preparation materials, documents, memories, tasks, hypotheses, and deterministic filter functions.
- Consumes: none.

- [ ] Write failing tests for combined job filters, expired status, preparation category filters, and empty results.
- [ ] Verify failures.
- [ ] Implement the smallest typed repository and filter functions that satisfy the tests.
- [ ] Verify tests pass.

### Task 4: Core Companion Pages

**Files:**
- Create: `frontend/src/pages/TodayPage.tsx`
- Create: `frontend/src/pages/ChatPage.tsx`
- Create: `frontend/src/pages/DreamingPage.tsx`
- Create: `frontend/src/pages/CompassPage.tsx`
- Create: `frontend/src/pages/JourneyPage.tsx`
- Create: `frontend/src/pages/MemoryPage.tsx`
- Create: `frontend/src/pages/SettingsPage.tsx`
- Create: `frontend/src/pages/core-pages.test.tsx`

**Interfaces:**
- Consumes: `AppShell`, `Bobo`, and demo repository types.
- Produces: routed page screens and primary interactions.

- [ ] Write failing route tests for page headings and Dreaming's dedicated state.
- [ ] Verify failures.
- [ ] Implement pages, interactive tabs/buttons, empty/loading affordances, and restrained glass layouts.
- [ ] Verify route tests pass.

### Task 5: Knowledge Base Pages

**Files:**
- Create: `frontend/src/pages/knowledge/KnowledgeLayout.tsx`
- Create: `frontend/src/pages/knowledge/JobsPage.tsx`
- Create: `frontend/src/pages/knowledge/PreparationPage.tsx`
- Create: `frontend/src/pages/knowledge/PersonalDocumentsPage.tsx`
- Create: `frontend/src/pages/knowledge/knowledge-pages.test.tsx`

**Interfaces:**
- Consumes: demo repository and filter functions from Task 3.
- Produces: `/knowledge/jobs`, `/knowledge/preparation`, and `/knowledge/personal` routes.

- [ ] Write failing interaction tests for job filters, preparation primary/secondary tabs, and personal upload category selection.
- [ ] Verify failures.
- [ ] Implement the data table, filters, detail drawers, material lists, upload modal, and visible demo-data badge.
- [ ] Verify interaction tests pass.

### Task 6: Chat API Adapter And Runtime States

**Files:**
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/api/chat.test.ts`
- Modify: `frontend/src/pages/ChatPage.tsx`

**Interfaces:**
- Produces: `sendChat(request, signal)` matching the current FastAPI `/v1/chat` schema.
- Consumes: `VITE_API_BASE_URL` and Bobo mood state.

- [ ] Write failing tests for request shape, response mapping, abort, and API error messages.
- [ ] Verify failures.
- [ ] Implement the adapter and wire Chat loading/success/error states to 泊泊.
- [ ] Verify tests pass.

### Task 7: Deployment, Accessibility, And Visual QA

**Files:**
- Create: `frontend/.env.example`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `frontend/vercel.json`
- Create: `frontend/README.md`
- Create: `design-qa.md`

**Interfaces:**
- Consumes: complete frontend.
- Produces: a reproducible production build and documented deployment configuration.

- [ ] Run unit tests, type checking, linting, and production build.
- [ ] Start the local preview and exercise navigation, filters, upload flow, chat error/success states, and Dreaming.
- [ ] Capture the implementation at the same desktop viewport as the source mock.
- [ ] Compare source and implementation, fix all P0/P1/P2 findings, and record `final result: passed` in `design-qa.md`.
- [ ] Re-run the full frontend and backend verification suites.
