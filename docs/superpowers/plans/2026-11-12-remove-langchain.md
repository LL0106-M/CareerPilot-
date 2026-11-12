# CareerPilot Remove LangChain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove LangChain completely and connect CareerPilot's existing Harness, tools, embeddings, memory analyzers, and evals directly to the official OpenAI Python SDK and CareerPilot-native contracts.

**Architecture:** `CareerPilotHarness` remains the only agent loop. A provider-neutral `ModelGateway` is implemented by an OpenAI-compatible adapter backed by `AsyncOpenAI`; all runtime tools implement `HarnessTool` directly; embeddings use the synchronous official `OpenAI` client to preserve the existing RAG contract.

**Tech Stack:** Python 3.12, `openai>=3,<4`, Pydantic, MCP Python SDK, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-11-12-remove-langchain-design.md`

## Global Constraints

- Preserve all existing user-visible tool names, descriptions, parameter fields, JSON result shapes, model temperatures, timeouts, and `max_retries=1`.
- Preserve MCP read-only fail-closed policy and `content_is_untrusted` results.
- Preserve Actions preview-confirm-apply; no tool added here may execute an external write.
- Preserve synchronous `EmbeddingProvider` and asynchronous `ModelGateway` contracts.
- Invalid or non-object model Tool Call arguments must fail before tool dispatch.
- Streaming must merge interleaved Tool Call fragments by index and tolerate missing usage.
- Do not send provider-specific stream usage options solely to obtain usage data.
- Do not overwrite, revert, stage, or commit unrelated existing worktree changes; this plan uses test checkpoints instead of commits because target files already contain user changes.
- Final benchmark floors: RAG Pass Rate >= 87.5%, Memory Pass Rate = 100%, hard failures = 0.

## Review Focus

- Interleaved streaming Tool Calls: fragments for two calls must assemble by index without mixing names, IDs, or JSON arguments; pinned in Task 1.
- Malformed Tool Call arguments: invalid JSON and valid non-object JSON must fail before any tool executes; pinned in Task 1.
- Duplicate tool names: overlays must reject duplicates instead of silently replacing tools; pinned in Task 2.
- MCP denial after discovery: an adapter whose policy changes before execution must return `forbidden` without calling the server; pinned in Task 4.
- Embedding response ordering: out-of-order SDK data must be restored by response index and count mismatches must fail; pinned in Task 7.

---

## File Structure

- `src/careerpilot/harness/model.py`: OpenAI-compatible `ModelGateway` adapter and message/response normalization.
- `src/careerpilot/agent/model.py`: model Gateway factories using `AsyncOpenAI`.
- `src/careerpilot/harness/tools.py`: native function tool and strict registry.
- `src/careerpilot/rag/tool.py`, `src/careerpilot/search/tool.py`, `src/careerpilot/actions/tool.py`, `src/careerpilot/mcp/adapter.py`: domain-specific `HarnessTool` factories/adapters.
- `src/careerpilot/agent/{base,runtime,service}.py`, `src/careerpilot/api/dependencies.py`, `src/careerpilot/mcp/platform.py`: native contract wiring.
- `src/careerpilot/memory/{dreaming_llm,direction_signals}.py`, `src/careerpilot/evaluation/agent_eval.py`: auxiliary generation through `ModelGateway`.
- `src/careerpilot/rag/embeddings.py`: synchronous official SDK embedding provider.
- `tests/harness/test_model.py`: provider adapter unit tests with injected fake SDK client.
- Existing domain tests: migrated from `.ainvoke()`/LangChain fakes to native contracts/fakes.

### Task 1: Native OpenAI-Compatible Model Gateway

**Files:**
- Modify: `src/careerpilot/harness/model.py`
- Modify: `src/careerpilot/agent/model.py`
- Create: `tests/harness/test_model.py`
- Modify: `tests/agent/test_runtime.py`

**Interfaces:**
- Consumes: existing `ModelGateway`, `ModelRequest`, `ModelResponse`, `ModelStreamEvent`, `HarnessMessage`, `ToolCall`.
- Produces: `OpenAICompatibleModelGateway(client: AsyncOpenAI, *, model: str, temperature: float)` implementing `generate()` and `stream()`; model factories returning `ModelGateway`.

- [ ] **Step 1: Write failing provider-adapter tests**

Add tests for text response, single and multiple Tool Calls, usage/finish reason, invalid JSON arguments, non-object arguments, streamed text, interleaved streamed Tool Calls, missing streamed usage, and empty stream. Inject a fake object exposing `chat.completions.create(...)`; assert invalid arguments raise before producing a final response.

- [ ] **Step 2: Run the new tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests\harness\test_model.py -q`

Expected: FAIL because `OpenAICompatibleModelGateway` does not exist.

- [ ] **Step 3: Implement the native Gateway**

Replace LangChain imports and `LangChainModelGateway` with `OpenAICompatibleModelGateway`. Add private conversion helpers for Harness messages, tool schemas, non-stream choices, streaming accumulation, JSON-object argument validation, and usage normalization. Do not add retries outside the SDK.

- [ ] **Step 4: Switch model factories to the official SDK**

In `agent/model.py`, create `AsyncOpenAI(api_key=..., base_url=..., timeout=..., max_retries=1)` and return configured Gateways from `create_exploration_model`, `create_reasoning_model`, `create_dreaming_model`, and `create_qwen_model`.

- [ ] **Step 5: Replace LangChain runtime fakes**

Update `tests/agent/test_runtime.py` to use a small fake `ModelGateway` or the provider fake from the new tests; retain the same Harness behavior assertions.

- [ ] **Step 6: Verify the model slice**

Run: `.venv\Scripts\python.exe -m pytest tests\harness\test_model.py tests\agent\test_runtime.py tests\harness\test_harness_runtime.py -q`

Expected: PASS.

### Task 2: Native Harness Tools and Strict Registry

**Files:**
- Modify: `src/careerpilot/harness/tools.py`
- Modify: `tests/harness/test_harness_runtime.py`
- Create: `tests/harness/test_tools.py`

**Interfaces:**
- Consumes: `HarnessTool`, `ToolSchema`.
- Produces: `FunctionHarnessTool(schema: ToolSchema, handler: Callable[..., object])`; `ToolRegistry` accepting and overlaying `HarnessTool` tuples.

- [ ] **Step 1: Write failing native-tool tests**

Test synchronous handler, asynchronous handler, string/JSON-serializable output, sanitized `ToolExecutionError`, policy deny/not-found, and duplicate-name rejection in constructor and overlay.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests\harness\test_tools.py -q`

Expected: FAIL because `FunctionHarnessTool` and duplicate rejection are absent.

- [ ] **Step 3: Implement native tool and registry**

Remove `BaseTool`, `LangChainToolAdapter`, and `from_langchain`. Implement explicit schema storage, sync/async handler dispatch, JSON normalization, exception chaining without exposing raw exception text, and duplicate-name validation.

- [ ] **Step 4: Update Harness tests to native tools**

Replace LangChain test tools with `FunctionHarnessTool` or a minimal fake `HarnessTool`.

- [ ] **Step 5: Verify the tool core**

Run: `.venv\Scripts\python.exe -m pytest tests\harness\test_tools.py tests\harness\test_harness_runtime.py -q`

Expected: PASS.

### Task 3: Migrate Search and RAG Tools

**Files:**
- Modify: `src/careerpilot/search/tool.py`
- Modify: `src/careerpilot/rag/tool.py`
- Modify: `tests/search/test_web_search_tool.py`
- Modify: `tests/rag/test_tool.py`
- Modify: `tests/rag/test_agentic_tool.py`

**Interfaces:**
- Consumes: Task 2 `FunctionHarnessTool` and `ToolSchema`.
- Produces: `build_web_search_tool`, `build_rag_tool`, and `build_agentic_rag_tool` returning `HarnessTool` with unchanged names, schemas, and JSON results.

- [ ] **Step 1: Convert tests to the native execution contract**

Change `.ainvoke(arguments)` to `.execute(arguments)` and add exact schema assertions for tool names and required parameter fields before changing production code.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests\search\test_web_search_tool.py tests\rag\test_tool.py tests\rag\test_agentic_tool.py -q`

Expected: FAIL because current builders return `StructuredTool`.

- [ ] **Step 3: Implement native Search and RAG tools**

Replace `StructuredTool.from_function` with `FunctionHarnessTool`. Encode defaults and optional fields in explicit JSON Schemas while preserving handler behavior and output JSON.

- [ ] **Step 4: Verify Search and RAG**

Run: `.venv\Scripts\python.exe -m pytest tests\search tests\rag -q`

Expected: PASS.

### Task 4: Migrate Actions and MCP Tools

**Files:**
- Modify: `src/careerpilot/actions/tool.py`
- Modify: `src/careerpilot/mcp/adapter.py`
- Modify: `src/careerpilot/mcp/platform.py`
- Modify: `tests/actions/test_tool.py`
- Modify: `tests/mcp/test_adapter.py`
- Modify: `tests/mcp/test_platform.py`

**Interfaces:**
- Consumes: Task 2 native tool contract.
- Produces: Action builders and `McpToolAdapter.as_harness_tool() -> HarnessTool`; `McpToolPlatform.runtime_tools() -> tuple[HarnessTool, ...]`.

- [ ] **Step 1: Convert and extend tests**

Use `.execute()` and schema assertions. Add a test that changes/denies policy after discovery and asserts the MCP client's `call_tool` was not invoked. Preserve Action preview-only assertions and MCP untrusted-content assertions.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests\actions\test_tool.py tests\mcp\test_adapter.py tests\mcp\test_platform.py -q`

Expected: FAIL because native adapters are absent.

- [ ] **Step 3: Implement native Action tools**

Return `FunctionHarnessTool` instances with explicit empty-object and preview payload schemas; do not expose `ActionService.apply`.

- [ ] **Step 4: Implement native MCP adapter**

Rename `as_langchain_tool` to `as_harness_tool`, return an object with the descriptor's namespaced schema, re-check policy at execution, and preserve bounded/untrusted JSON output.

- [ ] **Step 5: Verify Actions and MCP**

Run: `.venv\Scripts\python.exe -m pytest tests\actions tests\mcp -q`

Expected: PASS.

### Task 5: Rewire Agent and API Boundaries

**Files:**
- Modify: `src/careerpilot/agent/base.py`
- Modify: `src/careerpilot/agent/runtime.py`
- Modify: `src/careerpilot/agent/service.py`
- Modify: `src/careerpilot/api/dependencies.py`
- Modify: `tests/agent/test_service.py`
- Modify: `tests/api/test_dependencies.py`

**Interfaces:**
- Consumes: Tasks 1-4 `ModelGateway` and `HarnessTool` implementations.
- Produces: all factories and responder ports typed only with CareerPilot contracts.

- [ ] **Step 1: Change tests to native contracts**

Replace `BaseTool` annotations and `@tool` fakes with native fake `HarnessTool`; assert the same selected runtime tools reach the Agent and MCP discovery degradation remains non-fatal.

- [ ] **Step 2: Run the Agent/API tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests\agent tests\api\test_dependencies.py -q`

Expected: FAIL on current LangChain types and constructors.

- [ ] **Step 3: Rewire production types and constructors**

Make `CareerPilotResponder` accept a `ModelGateway`, build `ToolRegistry` directly, and accept native runtime tools. Update AgentService factories and API dependencies without altering the user's existing search/provider changes in overlapping files.

- [ ] **Step 4: Verify Agent/API wiring**

Run: `.venv\Scripts\python.exe -m pytest tests\agent tests\api\test_dependencies.py tests\api\test_chat.py -q`

Expected: PASS.

### Task 6: Migrate Auxiliary Model Consumers

**Files:**
- Modify: `src/careerpilot/memory/dreaming_llm.py`
- Modify: `src/careerpilot/memory/direction_signals.py`
- Modify: `src/careerpilot/evaluation/agent_eval.py`
- Modify: `tests/memory/test_dreaming_llm.py`
- Modify: `tests/memory/test_dreaming_daily_review.py`
- Modify: `tests/memory/test_direction_signals.py`
- Modify: `tests/evaluation/test_agent_eval.py`

**Interfaces:**
- Consumes: Task 1 `ModelGateway.generate(ModelRequest) -> ModelResponse`.
- Produces: Dreaming, direction detection, and evaluation with no provider-specific model types.

- [ ] **Step 1: Replace tests with scripted ModelGateway fakes**

Fakes record `ModelRequest`, return `ModelResponse(text=...)`, and preserve assertions for system/user prompt separation and JSON parsing.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests\memory\test_dreaming_llm.py tests\memory\test_dreaming_daily_review.py tests\memory\test_direction_signals.py tests\evaluation\test_agent_eval.py -q`

Expected: FAIL while production classes still require `BaseChatModel`.

- [ ] **Step 3: Migrate auxiliary consumers**

Replace LangChain messages and `.ainvoke()` with `HarnessMessage`, `ModelRequest`, and `ModelGateway.generate()`. Preserve current JSON extraction and fallback behavior.

- [ ] **Step 4: Verify memory/eval slice**

Run: `.venv\Scripts\python.exe -m pytest tests\memory tests\evaluation -q`

Expected: PASS.

### Task 7: Migrate Embeddings to Official SDK

**Files:**
- Modify: `src/careerpilot/rag/embeddings.py`
- Modify: `tests/test_embedding_service.py`
- Modify: `tests/test_config.py`
- Create or Modify: `tests/rag/test_embeddings.py`

**Interfaces:**
- Consumes: official synchronous `OpenAI.embeddings.create`.
- Produces: unchanged synchronous `EmbeddingProvider`; `OpenAICompatibleEmbeddingProvider` restoring response order by index.

- [ ] **Step 1: Write failing embedding adapter tests**

Test batch sizing, query instruction, empty input, out-of-order indexed response restoration, missing index/count mismatch, and float vector preservation with an injected fake embeddings client.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests\rag\test_embeddings.py tests\test_embedding_service.py -q`

Expected: FAIL because the native provider is absent.

- [ ] **Step 3: Implement native embedding provider**

Replace `OpenAIEmbeddings` with an injected client exposing `create`. `create_embedding_provider` constructs official `OpenAI`; batches documents, requests `encoding_format="float"`, sorts response data by index, and validates cardinality.

- [ ] **Step 4: Verify embedding and RAG regression**

Run: `.venv\Scripts\python.exe -m pytest tests\rag tests\test_embedding_service.py tests\test_config.py -q`

Expected: PASS.

### Task 8: Dependency Cleanup and Full Verification

**Files:**
- Modify: `pyproject.toml`
- Modify mechanically: `uv.lock`
- Modify as required: any remaining tests/docs that import runtime LangChain types
- Delete if empty/obsolete: LangChain-only adapters superseded in earlier tasks

**Interfaces:**
- Consumes: all prior tasks.
- Produces: repository with direct `openai>=3,<4` dependency and zero LangChain runtime/test references.

- [ ] **Step 1: Change dependencies**

Replace `langchain-openai>=0.3,<2` with `openai>=3,<4`; refresh `uv.lock` using the existing uv environment/cache.

- [ ] **Step 2: Prove LangChain is absent**

Run: `rg -n "langchain|BaseChatModel|BaseTool|StructuredTool|ChatOpenAI|OpenAIEmbeddings" src tests scripts pyproject.toml`

Expected: no matches.

- [ ] **Step 3: Run focused architecture tests**

Run: `.venv\Scripts\python.exe -m pytest tests\harness tests\agent tests\mcp tests\actions tests\rag tests\search tests\memory tests\evaluation -q`

Expected: PASS.

- [ ] **Step 4: Run the complete Python test suite**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: PASS.

- [ ] **Step 5: Run lint**

Run: `.venv\Scripts\python.exe -m ruff check src tests`

Expected: exit 0.

- [ ] **Step 6: Run the frozen offline benchmark**

Run: `.venv\Scripts\python.exe -m careerpilot.evaluation.system_benchmark --rag-dataset evals\rag\careerpilot-rag-seed-v1.json --memory-dataset evals\memory\careerpilot-memory-seed-v1.json --output-json .review\remove-langchain-benchmark.json --output-md .review\remove-langchain-benchmark.md`

Expected: RAG Pass Rate >= 87.5%, Memory Pass Rate = 100%, hard failures = 0.

- [ ] **Step 7: Inspect final diff and user-change preservation**

Run: `git diff --check` and `git status --short`

Expected: no whitespace errors; unrelated pre-existing modified/untracked files remain present and are not reverted or staged.
