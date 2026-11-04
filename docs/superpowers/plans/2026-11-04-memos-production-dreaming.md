# MemOS Production and Dreaming Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MemOS a real, observable auxiliary memory provider in production and document the complete online-memory plus Dreaming architecture.

**Architecture:** The local unified store remains canonical. Admitted successful turns are committed locally first and then written to MemOS; MemOS failure never rolls back the canonical write or the user reply. Dreaming consumes provenance-bound snapshots and emits hypotheses/reviews/patch proposals that pass policy and confirmation gates.

**Tech Stack:** Python 3.12, FastAPI, httpx, Pydantic Settings, SQLite, pytest.

**Spec:** `docs/architecture/agent-memory-handbook.md`

## Global Constraints

- MemOS keys stay server-side and are mandatory in production.
- Only successful turns admitted by local write policy reach MemOS.
- Local memory remains authoritative for status, deletion, sensitivity, and conflict resolution.
- MemOS outage degrades independently; it cannot fail a completed answer or local write.
- Dreaming output is evidence-bound and cannot silently become confirmed user memory.

## Review Focus

- A configured MemOS client must not be bypassed when the unified local store is enabled.
- A MemOS 5xx after a local commit must report cloud degradation while keeping the local write accepted.
- A failed/empty assistant run must write to neither local memory nor MemOS.
- Production configuration must reject a missing or malformed MemOS key.
- Dreaming hypotheses must retain evidence references and require confirmation before promotion.

### Task 1: MemOS provider contract and production configuration

**Files:** `src/careerpilot/config.py`, `src/careerpilot/memory/base.py`, `src/careerpilot/memory/memos.py`, `tests/test_config.py`, `tests/memory/test_memos.py`

- [x] Add failing tests for provider enabled state, documented filter/payload, and production key validation.
- [x] Run focused tests RED.
- [x] Implement the minimal provider/config contract.
- [x] Run focused tests GREEN.

### Task 2: Canonical-first MemOS dual write

**Files:** `src/careerpilot/harness/memory.py`, `src/careerpilot/agent/service.py`, `src/careerpilot/api/schemas.py`, `tests/harness/test_contextual_memory_pipeline.py`, `tests/agent/test_service.py`, `tests/api/test_chat.py`

- [x] Add failing tests for successful dual write, cloud-only degradation, skipped writes, and API observability.
- [x] Run focused tests RED.
- [x] Commit locally first, then call MemOS and expose `memory_provider_status`.
- [x] Run focused tests GREEN.

### Task 3: Complete engineering handbook

**Files:** `docs/architecture/agent-memory-handbook.md`

- [x] Document components, online read/write paths, Dreaming triggers/jobs/snapshots/outputs/application gates, MemOS boundaries, failure modes, deletion, and rollout checks.
- [x] Cross-check names against production code and tests.

### Task 4: Verification and resumed Journey work

- [x] Run full Python tests and MemOS live smoke test.
- [x] Resume `2026-11-04-compass-journey-knowledge-slice.md` from its existing RED tests.
