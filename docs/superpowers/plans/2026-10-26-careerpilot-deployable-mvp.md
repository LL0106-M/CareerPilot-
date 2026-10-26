# CareerPilot Deployable MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current full-stack MVP reproducibly deployable as one production service.

**Architecture:** Build React in a Node stage, copy the static output into a Python 3.12 runtime, and serve SPA plus API from FastAPI. Persist all SQLite/files under one mounted data directory and reject unsafe production defaults.

**Tech Stack:** React/Vite, FastAPI/Uvicorn, Python 3.12, Node 22, Docker/Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-26-careerpilot-deployable-mvp.md`

## Global Constraints

- One runtime container and one Uvicorn worker for the SQLite MVP.
- No secrets in image, frontend variables, repository, or logs.
- Existing `/v1` contracts remain unchanged.
- Production start fails on unsafe defaults.

## Review Focus

- SPA fallback must not turn missing APIs into HTML 200 responses.
- Persistent paths must stay below the mounted data root.
- Health checks must not require an external model call.
- Proxy deployment must preserve secure owner cookies.
- Uploads must be bounded before parsing.

---

### Task 1: Production configuration and static application

**Files:**
- Modify: `src/careerpilot/config.py`
- Create: `src/careerpilot/api/static.py`
- Modify: `src/careerpilot/api/app.py`
- Test: `tests/test_config.py`, `tests/api/test_static_app.py`, `tests/api/test_documents.py`

**Interfaces:**
- Produces: `Settings.frontend_dist_path`, `Settings.max_upload_bytes`, production validation, `SPAStaticFiles`.

- [ ] Write failing tests for unsafe production defaults, SPA routes/API 404 behavior, readiness, and upload limit.
- [ ] Run focused tests and confirm failure.
- [ ] Implement the minimum configuration, static serving, readiness, and upload guard.
- [ ] Run focused tests and Ruff.

### Task 2: Container and release contract

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yaml`, `.env.production.example`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: production settings and `frontend/dist` contract from Task 1.
- Produces: one-image deployment and CI image build gate.

- [ ] Add multi-stage non-root image, persistent volume, health check, and explicit one-worker command.
- [ ] Add CI jobs for Python, frontend, and Docker build.
- [ ] Document secrets, volume, migration/backup limitations, and deploy commands.

### Task 3: Production-mode verification

**Files:**
- Create: `scripts/smoke_deployment.py`
- Modify: `.superpowers/sdd/2026-10-25-careerpilot-unified-web-implementation/progress.md`

**Interfaces:**
- Consumes: `/health`, `/ready`, SPA fallback, production settings.
- Produces: repeatable HTTP smoke command and recorded evidence.

- [ ] Build frontend and run complete focused backend/frontend checks.
- [ ] Start Uvicorn with production variables and a temporary persistent data root.
- [ ] Run smoke script against health, readiness, SPA deep link, and API 404.
- [ ] Record Docker runtime as CI-only validation when Docker is unavailable locally.
