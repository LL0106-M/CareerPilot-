# Aliyun Production Model and Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy CareerPilot's model configuration on Qwen3.7-Plus and expose governed Alibaba Cloud web search to the DeepAgents harness.

**Architecture:** Keep the main model on the OpenAI-compatible endpoint and implement DashScope native multimodal SSE search as an explicit tool. Register the tool only when search credentials exist; AgentService controls when the tool is visible.

**Tech Stack:** Python 3.12, Pydantic Settings, LangChain/DeepAgents, httpx, pytest

**Spec:** `docs/plans/2026-10-21-aliyun-production-model-search-design.md`

## Global Constraints

- Production model is `qwen3.7-plus-2026-05-26`; development may use `qwen3.7-plus`.
- Exploration temperature is `0.4`; reasoning temperature is `0.0`.
- Search uses DashScope multimodal generation SSE and returns source URLs.
- Search strategies are limited to `turbo` and `max`; no nested `agent` strategy.
- Secrets never enter tracked files.
- Listen mode must not expose RAG or web-search tools.
- Every completed task receives its own Git commit.

## Review Focus

- Missing search credentials must degrade cleanly without preventing application startup.
- A malformed SSE event must not crash the whole Agent request or fabricate a source.
- Duplicate URLs with fragments must collapse to one source.
- The search tool must reject unsupported strategies such as `agent`.
- Listen mode must not expose `search_web` even when the provider is configured.

---

### Task 1: Production model and search configuration

**Files:**
- Modify: `.env.example`
- Modify: `src/careerpilot/config.py`
- Modify: `tests/test_config.py`
- Modify: `tests/agent/test_model.py`

**Interfaces:**
- Produces: validated `Settings` fields for main model and optional DashScope search.
- Consumes: existing `create_exploration_model` and `create_reasoning_model` factories.

- [ ] Write failing tests for the Qwen3.7 production model, workspace URLs, search strategies, and optional credentials.
- [ ] Run the focused tests and confirm they fail because the settings fields/defaults are missing.
- [ ] Add the minimal settings and example environment variables.
- [ ] Run focused and full tests.
- [ ] Commit as `feat: configure Qwen3.7 Plus production runtime`.

### Task 2: DashScope SSE search provider

**Files:**
- Create: `src/careerpilot/search/__init__.py`
- Create: `src/careerpilot/search/models.py`
- Create: `src/careerpilot/search/aliyun.py`
- Create: `tests/search/test_aliyun.py`

**Interfaces:**
- Consumes: `Settings.dashscope_*` configuration from Task 1.
- Produces: `AliyunWebSearchProvider.search(query, strategy) -> WebSearchResponse`.

- [ ] Write failing tests for request construction, source extraction, URL deduplication, malformed events, and HTTP errors using `httpx.MockTransport`.
- [ ] Run the focused tests and confirm failure because the provider does not exist.
- [ ] Implement models, SSE parsing, and the async provider with no SDK dependency.
- [ ] Run focused and full tests.
- [ ] Commit as `feat: add Alibaba Cloud web search provider`.

### Task 3: Governed DeepAgents search tool

**Files:**
- Create: `src/careerpilot/search/tool.py`
- Create: `tests/search/test_tool.py`
- Modify: `src/careerpilot/api/dependencies.py`
- Modify: `src/careerpilot/agent/service.py`
- Modify: `tests/agent/test_service.py`

**Interfaces:**
- Consumes: `AliyunWebSearchProvider` from Task 2.
- Produces: `search_web` StructuredTool registered only when configured.

- [ ] Write failing tests for untrusted JSON output, strategy validation, optional registration, and listen-mode denial.
- [ ] Run focused tests and confirm the intended failures.
- [ ] Implement the tool, conditional dependency wiring, and service allowlist.
- [ ] Run focused and full tests.
- [ ] Commit as `feat: expose governed web search to CareerPilot agent`.

### Task 4: Local secret configuration and live smoke checks

**Files:**
- Local-only: `.env`
- Modify: `README.md`

**Interfaces:**
- Consumes: deployed model and search endpoints from Tasks 1-3.
- Produces: reproducible setup instructions and live smoke evidence.

- [ ] Configure the supplied key and workspace URLs in ignored `.env` without printing the key.
- [ ] Run one minimal model request and one `turbo` search request against Alibaba Cloud.
- [ ] Document setup, cost boundary, key rotation advice, and smoke commands.
- [ ] Run the complete test suite, Ruff, compile check, and a secret-file scan.
- [ ] Commit tracked documentation as `docs: document Alibaba Cloud deployment`.
