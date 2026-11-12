# Governed MemOS Memory Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace keyword-to-active writes with a governed schema/patch pipeline, make MemOS the semantic data plane, and migrate existing memory safely.

**Architecture:** A deterministic safety prefilter and schema extractor create typed claims; a patch planner and admission gate decide local lifecycle changes; committed canonical claims alone sync to MemOS. SQLite remains a compact lifecycle/evidence/provider ledger and deterministic fallback.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, httpx, OpenAI-compatible model gateway, pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-governed-memos-memory-pipeline-design.md`

**Implementation status (2026-11-13):** All eight tasks implemented and verified. The checklists
below are retained as the execution record; verification evidence is summarized in the handoff.

## Global Constraints

- Preserve unrelated untracked `.benchmark-work/`, `config/mcp.servers.json`, and `data/actions/` content.
- Do not add OpenViking as a dependency.
- Marker presence alone never authorizes active memory.
- Only completed verified turns may enter extraction.
- Raw turns never go to MemOS; only admitted canonical claims do.
- Sensitive or inferred claims remain candidates until confirmed.
- Local pause/delete/owner decisions override every MemOS result.
- Every schema migration is idempotent and non-destructive.

## Review Focus

- Injection text containing “记住” must be rejected and never reach MemOS.
- A third-party preference must not become the current user's preference.
- Temporary distress with an explicit remember request must not become durable semantic memory.
- MemOS results without an active local mapping must not enter the prompt.
- A local deletion must block recall before provider deletion succeeds.

---

### Task 1: Claim, decision, and patch contracts

**Files:**
- Create: `src/careerpilot/memory/contracts.py`
- Create: `tests/memory/test_admission_contracts.py`

**Interfaces:**
- Produces: `MemoryClaim`, `MemoryPatch`, `AdmissionResult`, `AdmissionDecision`, `PatchOperation`, `MemorySubject`, `MemoryDurability`, and stable reason codes.
- Consumes: existing `MemoryType`, `MemorySensitivity`, and `MemoryConfidence`.

- [ ] Write failing contract validation tests, including required evidence and normalized bounded content.
- [ ] Run `python -m pytest tests/memory/test_admission_contracts.py -q` and confirm RED.
- [ ] Implement immutable Pydantic/dataclass contracts with the exact enums from the spec.
- [ ] Run the focused tests and confirm GREEN.

### Task 2: Deterministic safety prefilter and admission gate

**Files:**
- Create: `src/careerpilot/memory/admission_policy.py`
- Modify: `src/careerpilot/memory/write_policy.py`
- Create: `tests/memory/test_admission_policy.py`
- Modify: `tests/memory/test_write_policy.py`

**Interfaces:**
- Consumes: `MemoryClaim` and the raw source message.
- Produces: `MemorySafetyPrefilter.inspect(text) -> SafetyAssessment` and `MemoryAdmissionGate.decide(claim, source_text) -> AdmissionResult`.

- [ ] Add RED tests for injection, credentials, third-party subject, temporary distress, sensitive data, explicit durable preference, and inferred hypotheses.
- [ ] Run focused tests and confirm the current marker policy fails adversarial cases.
- [ ] Implement prefilter and gate; retain `MemoryWritePolicy` only as a conservative deterministic fallback extractor.
- [ ] Run focused tests and confirm GREEN.

### Task 3: Schema-driven extraction and patch planning

**Files:**
- Create: `src/careerpilot/memory/extractor.py`
- Create: `src/careerpilot/memory/patch_planner.py`
- Create: `tests/memory/test_memory_extractor.py`
- Create: `tests/memory/test_patch_planner.py`

**Interfaces:**
- Produces: `MemoryClaimExtractor.extract(turn) -> tuple[MemoryClaim, ...]`, `RuleBasedMemoryClaimExtractor`, `ModelMemoryClaimExtractor`, and `MemoryPatchPlanner.plan(owner_id, claims, active_records) -> tuple[MemoryPatch, ...]`.
- Consumes: existing `ModelGateway`, `ModelRequest`, `MemoryRecord`, and Task 1 contracts.

- [ ] Add RED tests for structured extraction, malformed model output, evidence bounds, exact duplicate `noop`, targeted correction, and conflict-to-pending behavior.
- [ ] Implement a rule-based fallback and a model-backed JSON extractor whose system prompt treats conversation text as untrusted evidence.
- [ ] Implement deterministic patch planning without fuzzy token-only supersession.
- [ ] Run extractor/planner tests and confirm GREEN.

### Task 4: Governance ledger and atomic patch application

**Files:**
- Modify: `src/careerpilot/memory/unified_store.py`
- Modify: `src/careerpilot/memory/models.py`
- Modify: `src/careerpilot/memory/service.py`
- Create: `tests/memory/test_governance_ledger.py`
- Modify: `tests/memory/test_memory_service.py`

**Interfaces:**
- Produces: provider sync rows, patch audit rows, `MemoryService.apply_patch_plan(...)`, and local-first provider lifecycle methods.
- Consumes: Task 1 patches/decisions and existing revision/evidence transactions.

- [ ] Add RED tests for schema upgrade, owner isolation, atomic multi-patch application, skipped/rejected audit, sync-state transitions, and local-first deletion.
- [ ] Add idempotent tables/indexes without deleting existing rows.
- [ ] Implement atomic patch application and bounded display/cache projection.
- [ ] Run unified-store and service tests and confirm GREEN.

### Task 5: Canonical-claim MemOS adapter and governed retrieval

**Files:**
- Modify: `src/careerpilot/memory/base.py`
- Modify: `src/careerpilot/memory/memos.py`
- Create: `src/careerpilot/memory/provider_service.py`
- Modify: `tests/memory/test_memos.py`
- Create: `tests/memory/test_provider_service.py`

**Interfaces:**
- Produces: `write_claim`, `list_memories`, `delete_memories`, reconciliation, and mapped-only governed search.
- Consumes: provider sync ledger and canonical local records.

- [ ] Add RED tests proving raw assistant/user turns are absent from payloads, local IDs are metadata, unmapped results are excluded, failures are retryable, and deletes target exact provider IDs.
- [ ] Extend the provider protocol and MemOS HTTP adapter using documented `/add/message`, `/search/memory`, `/get/memory`, and `/delete/memory` endpoints.
- [ ] Implement reconciliation and governed mapped-only search with local fallback.
- [ ] Run provider tests and confirm GREEN.

### Task 6: Integrate the governed lifecycle with Agent context

**Files:**
- Modify: `src/careerpilot/harness/memory.py`
- Modify: `src/careerpilot/harness/context.py`
- Modify: `src/careerpilot/agent/service.py`
- Modify: `src/careerpilot/api/dependencies.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `tests/harness/test_contextual_memory_pipeline.py`
- Modify: `tests/harness/test_unified_memory_context.py`
- Modify: `tests/agent/test_service.py`

**Interfaces:**
- Consumes: Tasks 2–5.
- Produces: completed-turn extraction/patch/admission/sync and MemOS-first governed retrieval with local fallback.

- [ ] Add RED end-to-end tests for rejected injection, pending sensitive claim, committed preference, provider degradation, mapped recall, and local delete dominance.
- [ ] Replace `remember_many_from_conversation` plus raw `add_turn` with the governed pipeline.
- [ ] Wire the reasoning model extractor in production dependencies and deterministic fallback in tests/no-model configurations.
- [ ] Run harness, agent, and API tests and confirm GREEN.

### Task 7: Existing-memory migration and cleanup report

**Files:**
- Create: `src/careerpilot/memory/migration.py`
- Create: `scripts/migrate_governed_memory.py`
- Create: `tests/memory/test_governed_memory_migration.py`
- Modify: `docs/architecture/agent-memory-handbook.md`

**Interfaces:**
- Produces: `GovernedMemoryMigrator.run(dry_run: bool) -> MigrationReport` and a CLI with dry-run default plus explicit `--apply`.
- Consumes: Tasks 2, 4, and 5.

- [ ] Add RED tests for dry-run immutability, owner-scoped dedupe, injection quarantine, safe sync enqueue, idempotent rerun, and audit/report counts.
- [ ] Implement the migrator and CLI; never automatically delete legacy rows or perform remote deletion.
- [ ] Update the handbook with the new write/read/migration contracts and OpenViking-inspired boundaries.
- [ ] Run migration tests and a dry run against a copy of the current database.

### Task 8: Evaluation datasets and full verification

**Files:**
- Modify: `evals/memory/careerpilot-memory-seed-v1.json`
- Modify: `src/careerpilot/evaluation/system_benchmark.py`
- Modify: `tests/evaluation/test_system_benchmark.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: trust-focused benchmark results and documented configuration.

- [ ] Add benchmark cases for injection, third-party attribution, transient explicit remember, sensitive confirmation, conflict, mapped-only recall, and deletion leakage.
- [ ] Update benchmark metrics with admission precision and unsafe-write count while preserving existing report fields.
- [ ] Run memory, harness, agent, API, evaluation, RAG, and frontend suites.
- [ ] Inspect the final diff for leaked credentials, unrelated changes, raw-turn MemOS writes, and destructive migration behavior.
