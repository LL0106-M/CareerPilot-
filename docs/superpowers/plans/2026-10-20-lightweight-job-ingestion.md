# Lightweight Job Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight, reusable job-intelligence Skill and an incremental JSON-to-RAG ingestion pipeline.

**Architecture:** External tools discover and fetch job pages; CareerPilot validates normalized records, skips unchanged content by hash, converts accepted records into structured RAG documents, and indexes them with the existing `RagIndexer`.

**Tech Stack:** Python 3.12, dataclasses, SQLite, existing CareerPilot RAG, Codex Skill Markdown.

**Spec:** `docs/plans/2026-10-20-lightweight-job-ingestion-design.md`

## Global Constraints

- Do not add Mage as a runtime dependency.
- Preserve source URL, verification status, and source level in every indexed job.
- Do not infer missing deadlines, establishment types, or verification state.
- All new production behavior starts with a failing test.

## Review Focus

- Duplicate records in one batch must not rebuild the same document.
- An unchanged source must not regenerate embeddings or chunks.
- Invalid source levels and missing identity fields must be rejected.
- Tracking parameters must not create duplicate source identities.
- Non-private employment channels must remain explicit instead of collapsing into generic campus recruitment.

---

### Task 1: Job record normalization

**Files:**
- Create: `src/careerpilot/ingestion/jobs.py`
- Test: `tests/ingestion/test_jobs.py`

**Interfaces:**
- Produces: `normalize_job_record(record, verified_at) -> JobRecord` and `job_to_document(job, fetched_at) -> SourceDocument`.

- [ ] Write failing tests for URL cleanup, explicit organization/employment types, stable identity, and missing required fields.
- [ ] Run the tests and confirm failures are caused by missing implementation.
- [ ] Implement minimal normalization and document conversion.
- [ ] Run the task tests and full suite.

### Task 2: Incremental ingestion pipeline

**Files:**
- Create: `src/careerpilot/ingestion/pipeline.py`
- Modify: `src/careerpilot/rag/store.py`
- Test: `tests/ingestion/test_pipeline.py`

**Interfaces:**
- Consumes: Task 1 normalization and document conversion.
- Produces: `JobIngestionPipeline.run(records, fetched_at) -> PipelineResult`.

- [ ] Write failing tests for indexed, unchanged, rejected, duplicate, and source-registry behavior.
- [ ] Run tests and confirm expected failures.
- [ ] Add the smallest store lookup and pipeline implementation.
- [ ] Run the task tests and full suite.

### Task 3: Product Skill and CLI

**Files:**
- Create: `skills/career-job-intelligence/SKILL.md`
- Create: `skills/career-job-intelligence/references/source-policy.md`
- Create: `skills/career-job-intelligence/references/job-record.schema.json`
- Create: `skills/career-job-intelligence/NOTICE.md`
- Create: `scripts/ingest_job_records.py`
- Test: `tests/ingestion/test_cli.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 2 pipeline.
- Produces: JSON-file CLI and reusable Skill contract for external Search/Fetch tools.

- [ ] Write a failing CLI integration test.
- [ ] Run it and confirm the entry point is absent.
- [ ] Add the Skill resources, attribution, and CLI.
- [ ] Validate the Skill, run CLI tests, full tests, lint, and compile checks.

