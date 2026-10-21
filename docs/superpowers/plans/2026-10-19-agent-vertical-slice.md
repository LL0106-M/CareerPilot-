# CareerPilot Agent Vertical Slice Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a locally runnable CareerPilot backend vertical slice that retrieves MemOS memories, applies the emotional-support policy, invokes a Deep Agents harness, and writes the completed turn back to MemOS.

**Architecture:** A FastAPI gateway calls an application service that owns orchestration. The service depends on explicit ports for long-term memory and the agent runtime. A MemOS HTTP adapter implements search-before/write-after. A Deep Agents factory supplies the production runtime while deterministic fakes keep tests local and provider-free. External RAG and action tools remain separate extension ports in this slice.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, httpx, Deep Agents, LangChain OpenAI-compatible model adapter, pytest, uv.

**Spec:** `PRD/CareerPilot-MVP-PRD.md`; `PRD/CareerPilot-Memory-RAG-Technical-Design.md`; `skills/career-emotional-support/SKILL.md`

---

## Global constraints

- Never place API keys in source, tests, examples, logs, or Git.
- MemOS search happens before model invocation; completed user/assistant turns are written afterward.
- A MemOS outage degrades personalization but does not fabricate memories or fail a safe chat response.
- Emotional support mode is enforced by code and prompt composition, not trusted to model self-restraint alone.
- MVP exposes no side-effecting external tools; action connectors must later use preview-confirm-apply-verify.
- The first slice must not download or run Qwen weights; it targets any OpenAI-compatible Qwen endpoint.

## Task 1: Project scaffold and configuration

**Produces:** installable Python package, validated environment settings, health endpoint.

1. Add `pyproject.toml`, `.env.example`, package folders, and API health test.
2. Run the health test and observe failure before production modules exist.
3. Implement settings and the FastAPI app factory minimally.
4. Run the focused test and the formatter/linter.

## Task 2: Emotional-support context policy

**Consumes:** request message and optional user-selected support mode.
**Produces:** deterministic support state and system-context fragment consumed by Task 4.

1. Add behavioral tests for explicit listen/organize/explore/act routing and distress-first response constraints.
2. Observe failures.
3. Implement the mode router and load the repository Skill into the system prompt.
4. Run focused tests.

## Task 3: MemOS Cloud adapter

**Produces:** `MemoryStore` port, typed memory context, HTTP MemOS implementation.

1. Add adapter tests using `httpx.MockTransport` for request contract, response parsing, and API failure.
2. Observe failures.
3. Implement `/search/memory` and `/add/message` with Token auth, timeouts, and safe parsing.
4. Run focused tests.

## Task 4: Deep Agents runtime and application service

**Consumes:** Task 2 support context and Task 3 memory context.
**Produces:** one completed assistant turn with memory status metadata.

1. Add service tests proving order: search → agent → add, prompt injection, and graceful MemOS degradation.
2. Observe failures.
3. Implement the agent port, Deep Agents factory, OpenAI-compatible Qwen model factory, and orchestration service.
4. Run focused tests.

## Task 5: Chat API and runnable handoff

**Consumes:** Task 4 service.
**Produces:** `POST /v1/chat`, local run instructions, complete verification.

1. Add API contract tests for successful chat and validation errors.
2. Observe failures.
3. Wire dependencies and implement the endpoint.
4. Add concise README usage and architecture boundary notes.
5. Run the entire test suite, lint, and import smoke test.

## Review focus

- Verify no secret can be serialized or logged.
- Verify memory content is clearly delimited as untrusted context.
- Verify network errors do not become invented memory or false success.
- Verify support mode cannot silently escalate to action.
- Verify the production path actually constructs a Deep Agents graph.
