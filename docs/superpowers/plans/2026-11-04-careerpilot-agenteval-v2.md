# CareerPilot AgentEval v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a machine-validatable 20-task seed evaluation set organized by CareerPilot user journeys, plus documentation explaining how the cases were derived.

**Architecture:** Keep the existing v1 single-turn regression set unchanged. Add a v2 JSONL task format with a focused Python loader/validator, then author 20 frozen-environment tasks and verify coverage invariants in tests.

**Tech Stack:** Python 3.12, dataclasses, standard-library JSON, pytest, JSONL, Markdown

**Spec:** `docs/evaluation/careerpilot-agenteval-v2-construction.md`

## Global Constraints

- Use five business scenarios as primary categories; Memory, RAG, hypothesis update, tool execution, and authorization remain capability tags.
- The seed set contains exactly 20 tasks: four per business scenario.
- Task types contain exactly 8 `single_turn`, 7 `multi_turn`, and 5 `long_horizon` tasks.
- Use fictional users, frozen knowledge, and simulated tools only.
- Preserve `evals/agent/careerpilot-agent-v1.jsonl` and its runner behavior.
- Unauthorized external writes, cross-user memory access, fabricated tool success, fabricated current facts, harmful memory promotion, and missed crisis routing are hard failures.

## Review Focus

- A malformed JSONL row should identify its file and line number.
- Duplicate task IDs must fail validation.
- Missing business-scenario coverage or an incorrect task-type quota must fail dataset validation.
- Every task must have at least one deterministic grader and one hard-failure condition.
- Every action-execution task must explicitly assert authorization behavior.

---

### Task 1: v2 task loader and validation contract

**Files:**
- Create: `src/careerpilot/evaluation/task_dataset.py`
- Test: `tests/evaluation/test_task_dataset.py`

**Interfaces:**
- Produces: `load_task_cases(path: Path) -> list[TaskCase]`
- Produces: `validate_seed_dataset(cases: Sequence[TaskCase]) -> None`

- [x] **Step 1: Write failing tests for valid loading, malformed line diagnostics, duplicate IDs, coverage quotas, grader requirements, and authorization checks.**
- [x] **Step 2: Run `pytest tests/evaluation/test_task_dataset.py -q` and confirm failure because the module is absent.**
- [x] **Step 3: Implement the minimal dataclasses, parser, per-case validation, and seed-set validation.**
- [x] **Step 4: Run `pytest tests/evaluation/test_task_dataset.py -q` and confirm all tests pass.**

### Task 2: author the 20-task seed dataset

**Files:**
- Create: `evals/agent/careerpilot-agent-v2.jsonl`
- Modify: `tests/evaluation/test_task_dataset.py`

**Interfaces:**
- Consumes: `load_task_cases` and `validate_seed_dataset` from Task 1.
- Produces: the canonical v2 seed dataset consumed by future runners.

- [x] **Step 1: Add a failing repository-dataset test asserting 20 unique tasks, 4 per scenario, task-type quota 8/7/5, control-variable metadata, deterministic graders, and hard-failure conditions.**
- [x] **Step 2: Run the focused test and confirm it fails because the dataset is absent.**
- [x] **Step 3: Add 20 cases covering emotional clarification, career exploration, external research, action execution, and long-term review.**
- [x] **Step 4: Run `pytest tests/evaluation/test_task_dataset.py -q` and confirm all tests pass.**

### Task 3: documentation and repository verification

**Files:**
- Verify: `docs/evaluation/careerpilot-agenteval-v2-construction.md`
- Verify: `evals/agent/careerpilot-agent-v2.jsonl`
- Verify: `src/careerpilot/evaluation/task_dataset.py`
- Verify: `tests/evaluation/test_task_dataset.py`

**Interfaces:**
- Consumes: the validated dataset and its loader.
- Produces: a human-readable construction record and reproducible verification evidence.

- [x] **Step 1: Check the construction document against the dataset fields, quotas, control pairs, hard failures, and stated limitations.**
- [x] **Step 2: Run focused tests and Ruff on the new Python files.**
- [x] **Step 3: Run the complete Python test suite and report any pre-existing or unrelated failures explicitly.**
- [x] **Step 4: Review the final diff for accidental edits to v1 or unrelated user changes.**
