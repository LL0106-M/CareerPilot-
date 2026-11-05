# Journey Future Letter Implementation Plan

**Goal:** Add an owner-scoped, single-model-call future letter with three paths to the existing Journey page.

**Architecture:** A focused future-letter service validates structured model output and stores artifacts in the product database. FastAPI exposes generate and confirm-takeaway endpoints. React renders an expandable glass panel while preserving all existing Journey controls.

**Tech Stack:** FastAPI, SQLite, provider-neutral ModelGateway, React, TypeScript, Vitest, pytest.

---

### Task 1: Domain and persistence

- Add failing tests for exactly-three-path validation, single generation call, owner scoping, and explicit takeaway confirmation.
- Implement future-letter models, parser, generator adapter, and ProductStore persistence.

### Task 2: API

- Add failing authenticated API tests for generation, ownership, and takeaway confirmation.
- Add request schemas, service dependency wiring, and endpoints.

### Task 3: Journey interface

- Add failing UI tests for opening the feature, switching among three paths, preserving the route, and confirming a takeaway.
- Add typed API methods and the glass future-letter panel.

### Task 4: Verification

- Run targeted backend and frontend tests, then full backend tests, frontend typecheck/build, and design QA where browser capture is available.

