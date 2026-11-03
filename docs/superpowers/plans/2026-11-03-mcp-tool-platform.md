# CareerPilot MCP Tool Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only, context-bounded MCP host layer that lets CareerPilot discover and call local STDIO or remote Streamable HTTP tools through its existing agent harness.

**Architecture:** The official MCP Python SDK v2 handles protocol and transport. CareerPilot normalizes discovered tools into namespaced descriptors, filters them through a fail-closed policy, selects a small query-relevant subset, and adapts them into the existing per-turn LangChain tool overlay.

**Tech Stack:** Python 3.12, official `mcp` Python SDK v2, Pydantic, LangChain Core tools, pytest, Ruff

**Spec:** `docs/superpowers/specs/2026-11-03-mcp-tool-platform-design.md`

## Global Constraints

- Support `stdio` and `streamable_http` behind one client contract.
- Use `mcp>=2.3,<3`; do not implement the JSON-RPC wire protocol manually.
- Name model-visible tools `mcp__<server_name>__<tool_name>`.
- Expose only tools explicitly annotated read-only and not destructive.
- Treat missing risk annotations as denied.
- Select at most eight MCP tools per turn by default.
- Mark every MCP result `content_is_untrusted=true` and bound its serialized size.
- Do not forward the complete host environment to STDIO subprocesses.
- Do not implement write tools, OAuth, search deployment, resources, prompts, sampling, or Apps.
- Preserve the dirty `main` checkout by working only in the isolated worktree.

## Review Focus

- A server marks a destructive tool read-only: destructive wins and the tool remains hidden; pinned to Task 2.
- A server returns duplicate tool names or a malformed schema: valid tools remain usable and the invalid entry is skipped; pinned to Task 3.
- A remote or STDIO server is unavailable: discovery fails soft and internal tools remain available; pinned to Task 4.
- A tool returns a very large result or credential-shaped error: output is bounded and secrets are absent; pinned to Task 3.
- A query matches many tools or no tools: selection is deterministic, capped at eight, and never falls back to exposing all; pinned to Task 2.

---

### Task 1: Configuration and protocol-neutral models

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/careerpilot/config.py`
- Create: `src/careerpilot/mcp/__init__.py`
- Create: `src/careerpilot/mcp/models.py`
- Create: `src/careerpilot/mcp/config.py`
- Test: `tests/mcp/test_config.py`

**Interfaces:**
- Consumes: optional `CAREERPILOT_MCP_CONFIG_PATH` environment value.
- Produces: `McpServerConfig`, `McpToolDescriptor`, `McpToolResult`, `load_mcp_servers(path) -> tuple[McpServerConfig, ...]`.

- [ ] **Step 1: Write failing configuration tests**

Test valid STDIO and Streamable HTTP JSON definitions, transport-specific required fields, safe
loopback HTTP, non-loopback HTTPS enforcement, normalized names, and missing-file disablement.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `python -m pytest tests/mcp/test_config.py -q`

Expected: collection fails because `careerpilot.mcp` does not exist.

- [ ] **Step 3: Add the SDK dependency and implement models/config loading**

Add `mcp>=2.3,<3`. Implement Pydantic/dataclass models with explicit validation and
`Settings.mcp_config_path: Path | None` mapped from `CAREERPILOT_MCP_CONFIG_PATH`.

- [ ] **Step 4: Run configuration tests and Ruff**

Run: `python -m pytest tests/mcp/test_config.py -q`

Run: `python -m ruff check src/careerpilot/mcp src/careerpilot/config.py tests/mcp/test_config.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```powershell
git add pyproject.toml src/careerpilot/config.py src/careerpilot/mcp tests/mcp/test_config.py
git commit -m "feat: add MCP server configuration"
```

### Task 2: Fail-closed policy and bounded tool selection

**Files:**
- Create: `src/careerpilot/mcp/policy.py`
- Create: `src/careerpilot/mcp/catalog.py`
- Test: `tests/mcp/test_policy.py`
- Test: `tests/mcp/test_catalog.py`

**Interfaces:**
- Consumes: `McpServerConfig`, `McpToolDescriptor` from Task 1.
- Produces: `McpToolPolicy.allows(descriptor) -> bool`; `McpToolCatalog.select(query, descriptors, limit=8) -> tuple[McpToolDescriptor, ...]`.

- [ ] **Step 1: Write failing policy tests**

Test explicit read-only acceptance; unknown annotation, write, destructive, disabled server, and
allowlist exclusion rejection. Pin the contradictory read-only/destructive case.

- [ ] **Step 2: Run policy tests and confirm RED**

Run: `python -m pytest tests/mcp/test_policy.py -q`

Expected: FAIL because the policy module is missing.

- [ ] **Step 3: Implement the minimal policy and verify GREEN**

Implement `McpToolPolicy` as a pure fail-closed predicate and run the policy tests.

- [ ] **Step 4: Write failing catalog tests**

Test namespaced identity, deterministic lexical ranking, explicit-name priority, eight-tool cap,
empty/unrelated query returning none, and no duplicate model-visible names.

- [ ] **Step 5: Run catalog tests and confirm RED**

Run: `python -m pytest tests/mcp/test_catalog.py -q`

Expected: FAIL because the catalog module is missing.

- [ ] **Step 6: Implement selection and verify GREEN**

Tokenize case-insensitively, score exact/name/title/description/server matches with fixed weights,
sort by score then namespaced name, and exclude zero-score descriptors.

- [ ] **Step 7: Run Task 2 tests and commit**

Run: `python -m pytest tests/mcp/test_policy.py tests/mcp/test_catalog.py -q`

```powershell
git add src/careerpilot/mcp/policy.py src/careerpilot/mcp/catalog.py tests/mcp
git commit -m "feat: add MCP tool policy and selection"
```

### Task 3: Official SDK client, caching, and harness adapters

**Files:**
- Create: `src/careerpilot/mcp/client.py`
- Create: `src/careerpilot/mcp/adapter.py`
- Test: `tests/mcp/test_client.py`
- Test: `tests/mcp/test_adapter.py`
- Create: `tests/mcp/fixtures/read_only_server.py`

**Interfaces:**
- Consumes: Task 1 models and official `mcp.Client` / `StdioServerParameters`.
- Produces: `OfficialMcpClient.list_tools(force_refresh=False)`, `OfficialMcpClient.call_tool(name, arguments)`, `McpToolAdapter.as_langchain_tool()`.

- [ ] **Step 1: Write failing in-process client tests**

Use a real `MCPServer` passed to the official `Client`. Test paginated/normalized discovery where
applicable, structured result preference, text fallback, tool-level error conversion, duplicate or
malformed tool skipping, result bounding, and secret-free error messages.

- [ ] **Step 2: Run client tests and confirm RED**

Run: `python -m pytest tests/mcp/test_client.py -q`

Expected: FAIL because the client wrapper is missing.

- [ ] **Step 3: Implement the client wrapper and TTL descriptor cache**

Build targets from validated configs, open official clients with `async with`, paginate tools,
normalize annotations/schemas, cache by configuration fingerprint, and return safe typed results.

- [ ] **Step 4: Verify client GREEN**

Run: `python -m pytest tests/mcp/test_client.py -q`

- [ ] **Step 5: Write failing adapter tests**

Test namespaced schema exposure, original-name invocation, policy recheck at execution time,
untrusted result envelope, and stable forbidden/failed JSON.

- [ ] **Step 6: Implement adapter and verify GREEN**

Use `StructuredTool.from_function(coroutine=...)` with a dynamic Pydantic input model derived from
the descriptor schema, or a focused `BaseTool` subclass if dynamic schema preservation requires it.

- [ ] **Step 7: Add and run a real STDIO fixture test**

Launch `tests/mcp/fixtures/read_only_server.py` through `StdioServerParameters`; prove discovery and
one tool call complete without inheriting an unrelated sentinel secret environment variable.

- [ ] **Step 8: Run Task 3 tests, Ruff, and commit**

Run: `python -m pytest tests/mcp/test_client.py tests/mcp/test_adapter.py -q`

Run: `python -m ruff check src/careerpilot/mcp tests/mcp`

```powershell
git add src/careerpilot/mcp tests/mcp
git commit -m "feat: add MCP client and tool adapter"
```

### Task 4: Per-turn discovery and AgentService integration

**Files:**
- Create: `src/careerpilot/mcp/platform.py`
- Modify: `src/careerpilot/agent/service.py`
- Test: `tests/mcp/test_platform.py`
- Modify: `tests/agent/test_service.py`

**Interfaces:**
- Consumes: catalog, policy, client, and adapter from Tasks 1-3.
- Produces: `McpToolPlatform.runtime_tools(owner_id, query) -> tuple[BaseTool, ...]`; optional `AgentService.mcp_tool_factory` asynchronous callback.

- [ ] **Step 1: Write failing platform tests**

Test multi-server discovery, partial server outage, cache reuse, config fingerprint invalidation,
policy filtering before selection, and an eight-tool maximum.

- [ ] **Step 2: Run platform tests and confirm RED**

Run: `python -m pytest tests/mcp/test_platform.py -q`

Expected: FAIL because the platform module is missing.

- [ ] **Step 3: Implement the platform and verify GREEN**

Discover servers independently with bounded concurrency, keep successful descriptors when one
server fails, select permitted descriptors, and create adapters only for the selected subset.

- [ ] **Step 4: Write failing AgentService integration tests**

Test that selected MCP tools enter `runtime_tools` and `allowed_tool_names`, unrelated tools do not,
and discovery failure still yields a completed chat using existing internal behavior.

- [ ] **Step 5: Run integration tests and confirm RED**

Run: `python -m pytest tests/agent/test_service.py -q`

Expected: FAIL because `AgentService` has no MCP factory.

- [ ] **Step 6: Add the optional asynchronous factory and verify GREEN**

Call it after context compilation, add returned tools to the runtime overlay/allowed set, and catch
only MCP platform discovery errors so unrelated programming errors remain visible.

- [ ] **Step 7: Run Task 4 tests and commit**

Run: `python -m pytest tests/mcp/test_platform.py tests/agent/test_service.py -q`

```powershell
git add src/careerpilot/mcp/platform.py src/careerpilot/agent/service.py tests/mcp/test_platform.py tests/agent/test_service.py
git commit -m "feat: integrate MCP tools per agent turn"
```

### Task 5: Operator configuration, diagnostics, and final verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Create: `config/mcp.servers.example.json`
- Create: `scripts/inspect_mcp_tools.py`
- Test: `tests/scripts/test_inspect_mcp_tools.py`

**Interfaces:**
- Consumes: `load_mcp_servers` and `McpToolPlatform` from previous tasks.
- Produces: an offline-safe diagnostic CLI that lists policy-visible tools without invoking them.

- [ ] **Step 1: Write failing CLI behavior tests**

Run the script against a fixture STDIO server; assert exit 0 and safe tool metadata. Run invalid and
unavailable configs; assert nonzero exit and no secret values in stderr.

- [ ] **Step 2: Run CLI tests and confirm RED**

Run: `python -m pytest tests/scripts/test_inspect_mcp_tools.py -q`

Expected: FAIL because the script is missing.

- [ ] **Step 3: Implement diagnostic CLI and documentation**

Add an example config containing a disabled local demo and loopback HTTP example, document STDIO vs
HTTP, read-only annotations, allowlists, context cap, security, and the later search MCP phase.

- [ ] **Step 4: Run focused tests and lint**

Run: `python -m pytest tests/mcp tests/scripts/test_inspect_mcp_tools.py tests/agent/test_service.py -q`

Run: `python -m ruff check src scripts tests`

- [ ] **Step 5: Run the full backend suite**

Run: `python -m pytest -q`

Expected: all tests PASS; existing Starlette cookie deprecation warnings may remain.

- [ ] **Step 6: Inspect the scoped diff and perform a read-only review**

Review the spec, this plan, `pyproject.toml`, MCP package, AgentService integration, tests, example
config, script, and README. Confirm no unrelated checkout files appear.

- [ ] **Step 7: Commit Task 5**

```powershell
git add .env.example README.md config/mcp.servers.example.json scripts/inspect_mcp_tools.py tests/scripts/test_inspect_mcp_tools.py
git commit -m "docs: add MCP tool platform operations"
```

