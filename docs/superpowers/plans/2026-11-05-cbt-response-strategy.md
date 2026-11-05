# CBT-Informed Response Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make per-turn affect and CBT appraisal directly control CareerPilot's answer move, pressure, length, question, and Markdown presentation.

**Architecture:** Add a deterministic Python response-strategy component between intent interpretation and prompt composition. It produces an immutable response contract that is injected near the final answer instructions; existing safety, memory, retrieval, and action authorization stay authoritative.

**Tech Stack:** Python 3.12, dataclasses, pytest, existing CareerPilot Harness.

**Spec:** `docs/superpowers/specs/2026-11-05-cbt-response-strategy-design.md`

## Global Constraints

- No MBTI, diagnosis, therapy claims, Node runtime, or second memory store.
- CBT reframing activates only for supported negative automatic-thought signals.
- User-selected support mode and safety routing always override response strategy.
- Default presentation uses short Markdown paragraphs, restrained bold, optional bullets, and at most one question.
- Preserve unrelated dirty-worktree changes.

## Review Focus

- Tentative positive interest must not be misclassified as distress or action readiness.
- Negative self-judgment without a concrete fact must not be echoed as truth.
- Explicit action requests must not be blocked by the reflective strategy.
- Listen mode must not become a report with headings or a checklist.
- Empty or neutral text must receive a safe, compact default contract.

---

### Task 1: Derive a response contract

**Files:**
- Create: `src/careerpilot/support/response_strategy.py`
- Create: `tests/support/test_response_strategy.py`
- Modify: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Consumes: `ResponseStrategyEngine.derive(message: str, decision: SupportDecision, intent: TaskIntent) -> ResponseContract`
- Produces: `ResponseContract.as_prompt_context() -> str`

- [ ] **Step 1: Write failing strategy tests**

Cover tentative interest, negative automatic thought, explicit action mode, listen mode, and neutral fallback with literal assertions on response move, CBT activation, initiative, verbosity, question target, forbidden moves, and presentation policy.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/support/test_response_strategy.py -q`
Expected: FAIL because `careerpilot.support.response_strategy` does not exist.

- [ ] **Step 3: Implement the minimal response-strategy types and rules**

Create immutable `AffectAppraisal`, `CBTGuidance`, `PresentationContract`, and `ResponseContract` dataclasses plus `ResponseStrategyEngine`. Use conservative marker-based appraisal, with explicit support mode taking precedence.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `pytest tests/support/test_response_strategy.py -q`
Expected: all tests pass.

- [ ] **Step 5: Document third-party inspiration**

Add the upstream repository, MIT license, and the concepts independently reimplemented; do not claim vendored source when none is copied.

### Task 2: Inject the contract into generated prompts

**Files:**
- Modify: `src/careerpilot/agent/prompt.py`
- Modify: `src/careerpilot/harness/context.py`
- Create: `tests/agent/test_prompt.py`
- Modify: `tests/harness/test_unified_memory_context.py`

**Interfaces:**
- Consumes: `ResponseContract` from Task 1.
- Produces: `PromptComposer.compose(..., response_contract: ResponseContract | None = None) -> str` and `CompiledContext.response_contract`.

- [ ] **Step 1: Write failing prompt and compiler tests**

Assert that tentative-interest prompts include the reflective-exploration move, short Markdown rules, restrained bold, one-question limit, and prohibited intake/lecture behavior. Assert that CBT guidance appears for negative self-judgment and that the compiled context exposes the same contract.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/agent/test_prompt.py tests/harness/test_unified_memory_context.py -q`
Expected: FAIL because the composer and compiled context do not accept or expose the response contract.

- [ ] **Step 3: Wire strategy derivation into context compilation and prompt composition**

Derive once per turn after intent interpretation, store it on `CompiledContext`, and render it in a `<response_contract>` section immediately before final reply constraints.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `pytest tests/agent/test_prompt.py tests/harness/test_unified_memory_context.py -q`
Expected: all tests pass.

### Task 3: Regression verification

**Files:**
- Create: `frontend/src/components/chat/MessageContent.tsx`
- Create: `frontend/src/components/chat/MessageContent.test.tsx`
- Modify: `frontend/src/pages/chat/ChatPage.tsx`
- Modify: `frontend/src/styles/pages.css`
- Modify only files already listed if another regression is exposed.

**Interfaces:**
- Consumes: completed response-strategy integration.
- Produces: verified repository behavior.

- [ ] **Step 1: Run focused behavior tests**

Run: `pytest tests/support tests/context tests/harness/test_unified_memory_context.py tests/harness/test_contextual_memory_pipeline.py tests/agent/test_prompt.py -q`
Expected: all tests pass.

- [ ] **Step 2: Render the approved Markdown hierarchy safely**

Write the failing component tests first, then implement paragraphs, bold text, unordered
lists, and small headings without raw HTML rendering. Integrate the component into chat and
run `npm test -- src/components/chat/MessageContent.test.tsx src/pages/chat/ChatPage.test.tsx`.

- [ ] **Step 3: Run lint on changed Python files**

Run: `ruff check src/careerpilot/support/response_strategy.py src/careerpilot/agent/prompt.py src/careerpilot/harness/context.py tests/support/test_response_strategy.py tests/agent/test_prompt.py tests/harness/test_unified_memory_context.py`
Expected: no lint errors.

- [ ] **Step 4: Run the full Python suite and frontend production build**

Run: `pytest -q`
Expected: all tests pass; any unrelated pre-existing failure is reported by exact test name.

Run: `npm run typecheck && npm run build`
Expected: both commands exit successfully.
