# Relationship Profile and Memory Quality Phase 3 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give Bobo a stable character with user-controlled interaction style, then add memory consolidation and quality evaluation without turning personality guesses into career evidence.

**Architecture:** Explicit relationship preferences remain governed memories. `relationship_profiles` is a reversible projection with provenance and confidence across pace, structure, challenge, initiative, tone, and detail. Prompt assembly combines stable Bobo core, confirmed profile, and temporary support state. Maintenance services merge duplicate episodes and invalidate derived records when sources disappear.

**Tech Stack:** Python 3.12, SQLite, FastAPI, pytest, React 19, TypeScript, Vitest.

---

### Task 1: Add relationship profile projection

**Files:**
- Create: `src/careerpilot/relationship/__init__.py`
- Create: `src/careerpilot/relationship/models.py`
- Create: `src/careerpilot/relationship/service.py`
- Modify: `src/careerpilot/product_store.py`
- Create: `tests/relationship/test_service.py`

**RED:** Test allowed dimensions, onboarding/user-correction provenance, candidate versus confirmed status, repeated-signal thresholds, reset behavior, and strict separation from career evidence.

**GREEN:** Add `relationship_profiles` and a versioned stable Bobo core; compute projections from confirmed relationship memories and explicit choices.

**Verify:** `uv run pytest tests/relationship/test_service.py -q`

**Commit:** `feat(relationship): add user-controlled Bobo style profile`

### Task 2: Add lightweight situational onboarding and settings

**Files:**
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/pages/settings/SettingsPage.tsx`
- Create: `frontend/src/pages/settings/RelationshipSettings.test.tsx`
- Create: `tests/api/test_relationship_profile.py`

**RED:** Test four situational choices, partial completion, later edits, and one-click reset. Do not expose MBTI or fixed personality labels.

**GREEN:** Add concise setup/settings controls mapping directly to pace, challenge, detail, and callback initiative.

**Verify:** `uv run pytest tests/api/test_relationship_profile.py -q`; `npm test -- --run src/pages/settings/RelationshipSettings.test.tsx`

**Commit:** `feat(settings): add Bobo interaction preferences`

### Task 3: Apply adjacent matching in the prompt

**Files:**
- Modify: `src/careerpilot/harness/context.py`
- Modify: `src/careerpilot/agent/prompt.py`
- Modify: `tests/agent/test_prompt.py`
- Modify: `tests/context/test_router.py`

**RED:** Test confirmed style adaptation, candidate exclusion, temporary reduction of challenge in emotional distress, evidence-based disagreement, and unchanged safety boundaries.

**GREEN:** Compose stable core + relationship projection + temporary support adjustment with explicit provenance and limits.

**Verify:** `uv run pytest tests/agent/test_prompt.py tests/context/test_router.py -q`

**Commit:** `feat(agent): adapt Bobo style with bounded profiles`

### Task 4: Consolidate and evaluate long-term memory quality

**Files:**
- Create: `src/careerpilot/memory/maintenance.py`
- Create: `tests/memory/test_maintenance.py`
- Create: `evals/memory_quality_cases.json`
- Create: `tests/evaluation/test_memory_quality.py`
- Modify: `src/careerpilot/product_store.py`

**RED:** Test duplicate episode merge, conflicting evidence preservation, source deletion invalidation, callback precision, false-fact rate, and correction handling.

**GREEN:** Add deterministic maintenance operations and an offline rubric/report. Do not auto-delete source turns or silently overwrite contradictions.

**Verify:** `uv run pytest -q`; `npm test -- --run`; `npm run build`

**Commit:** `feat(memory): consolidate and evaluate long-term recall`

