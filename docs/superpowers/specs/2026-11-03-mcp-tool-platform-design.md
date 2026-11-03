# CareerPilot MCP Tool Platform Design

Date: 2026-11-03

## Intent

Make CareerPilot an MCP host without replacing its provider-neutral agent harness. The local
Qwen model continues to emit ordinary tool calls; CareerPilot discovers MCP tools, selects a
small relevant subset, enforces policy, invokes the server, and returns bounded results to the
model. The same integration must support local STDIO servers and remote Streamable HTTP servers.

## Goals

- Add a standards-based MCP client layer using the official Python SDK v2.
- Support local `stdio` and remote `streamable_http` connections behind one interface.
- Merge selected MCP tools into the existing per-turn `ToolRegistry` through LangChain adapters.
- Preserve the existing CareerPilot-owned model/tool loop and action governance boundary.
- Expose only explicitly read-only, non-destructive MCP tools in the first release.
- Discover tools lazily from the user query and cap the loaded set to protect the 4K context.
- Cache normalized tool descriptors with a bounded TTL and invalidate on configuration changes.
- Return structured, bounded, untrusted tool results and redact credentials from audit events.
- Verify behavior with an in-process real MCP server, not a mocked wire protocol.

## Non-goals

- No MCP write tools, user approval UI, OAuth flow, SearXNG deployment, or third-party account
  connection in this phase.
- No conversion of internal RAG, memory, or action tools into MCP.
- No MCP resources, prompts, sampling, elicitation, Apps UI, or server-initiated workflows.
- No hosted OpenAI or Claude MCP runtime dependency.
- No edits to the unrelated dirty `main` checkout.

## Alternatives Considered

### Local-only STDIO

This is the smallest path for a desktop Qwen deployment, but it would make later cloud hosting
and cross-client reuse harder. Rejected as the platform boundary, retained as a transport.

### Remote-only Streamable HTTP

This aligns with hosted OpenAI and Claude connectors, but forces local file and resume tools to
become network services and creates avoidable exposure. Rejected as the only transport.

### Hybrid client with one normalized registry (selected)

One host-side contract accepts either transport, normalizes tool metadata, applies one policy,
and exposes the same harness tools. This costs an additional adapter but avoids two security and
selection implementations.

## Architecture

```text
Qwen3-4B via llama.cpp
        |
        | ordinary OpenAI-compatible tool calls
        v
CareerPilotHarness
        |
        v
ToolRegistry overlay
  |-- internal RAG / memory / governed action preview
  `-- selected MCP tool adapters
           |
           v
McpToolPlatform
  |-- McpToolCatalog       discovery, normalization, TTL cache, lexical selection
  |-- McpToolPolicy        allowlist and read-only/destructive enforcement
  `-- McpClientManager     server lookup and invocation
           |
           +-- official MCP Client(StdioServerParameters)
           `-- official MCP Client("https://.../mcp")
```

CareerPilot remains the MCP host. Each configured server is represented by a server definition,
but the first implementation opens a bounded client session per discovery or invocation rather
than maintaining background connections. Descriptor caching avoids repeated `tools/list` calls
within the TTL. Persistent connection pooling can be added after measurements show it is needed.

## Components and Contracts

### Configuration

`McpServerConfig` contains a stable server name, description, transport, URL or command/arguments,
an optional environment allowlist, an allowed-tool list, timeout, descriptor TTL, and maximum
result characters. Validation requires exactly the fields needed by the chosen transport. The
configuration never contains bearer tokens; future authentication will reference secret names.

The application loads an optional JSON file named by `CAREERPILOT_MCP_CONFIG_PATH`. Missing config
means MCP is disabled, not an application startup failure. Invalid configured files fail closed
with a clear configuration error.

### Client

`OfficialMcpClient.list_tools()` paginates until `next_cursor` is absent and returns protocol tool
objects. `call_tool(name, arguments)` checks `is_error`, prefers `structured_content`, converts text
content blocks when needed, rejects unsupported binary blocks from model context, and returns a
normalized result. Transport and protocol exceptions become sanitized `McpConnectionError` or
`McpToolCallError` values; raw credentials and child-process environment values never enter errors.

### Catalog and selection

The catalog normalizes every tool to a namespaced name:

```text
mcp__<server_name>__<tool_name>
```

It stores the original server/tool identifiers separately for execution. Selection scores query
tokens against server description, tool name, title, and description. Explicit name matches rank
above description matches. Only tools permitted by the server allowlist and policy participate.
The result is deterministic and capped at eight tools by default. Empty or unrelated queries load
no MCP tools; the platform does not expose the entire catalog as a fallback.

### Policy

The first release requires all of the following before a tool reaches the model:

- the server is enabled;
- the tool is included in the configured allowlist when an allowlist exists;
- MCP annotations explicitly mark it read-only;
- it is not marked destructive;
- its namespaced identifier is not denied by application policy.

Missing annotations are treated as unknown risk and denied. Server-supplied annotations are hints,
not authority: the application allowlist remains mandatory for sensitive deployments. A later
write phase will reuse the existing preview-confirm-apply action service instead of bypassing it.

### Harness integration

`AgentService` receives an optional asynchronous MCP tool factory. After context and intent routing,
the factory receives the authenticated owner ID and current user message. It returns a small tuple
of LangChain-compatible tools, which are added to the existing runtime overlay and allowed-name
set. MCP failure is fail-soft: unavailable discovery yields no MCP tools and does not break chat.
A selected tool failure returns a structured tool error so the model can explain or recover.

## Data Flow

1. The user sends a message.
2. Existing context routing determines the support mode and internal tools.
3. The MCP platform tokenizes the message and consults its descriptor cache.
4. On cache miss it calls `tools/list` for enabled servers, paginating and normalizing results.
5. Policy removes unknown, write, destructive, and non-allowlisted tools.
6. Selection returns at most eight relevant descriptors.
7. Adapters are overlaid into the run's existing registry.
8. Qwen may emit a normal tool call using the namespaced name.
9. CareerPilot rechecks policy, calls the original MCP server tool, bounds the result, marks external
   content untrusted, and appends a normal harness tool message.
10. The harness continues its existing model/tool loop and audit events.

## Context, Cache, and Result Rules

- Tool schemas are loaded only for selected tools and are appended through the existing runtime
  overlay, preserving the stable model prompt prefix.
- Descriptor cache keys include the normalized server configuration fingerprint.
- Default descriptor TTL is five minutes; callers may force refresh for diagnostics.
- Default selected-tool cap is eight, intentionally below OpenAI's soft recommendation of twenty
  initial tools because the local model has a 4096-token context.
- Tool result JSON is capped per server. Oversized text is truncated with explicit metadata.
- Every external result contains `content_is_untrusted=true`.
- Images, audio, embedded resources, and arbitrary remote URLs are not automatically fetched.

## Error Handling

- Missing config: MCP disabled.
- Invalid config: fail startup/configuration validation with the server name and safe field error.
- Discovery timeout or unavailable server: record a sanitized diagnostic and continue with other
  servers and internal tools.
- Malformed tool schema: skip that tool, keep the server's valid tools.
- Tool rejected by policy: never expose it; direct execution returns `forbidden`.
- Protocol/tool error: return `failed` with safe server/tool identifiers, no traceback or secrets.
- Oversized output: return bounded content plus `truncated=true`.
- Duplicate names: namespaces prevent cross-server collision; duplicate names within one server are
  rejected during normalization.

## Testing Strategy

- Unit tests cover configuration invariants, naming, policy, deterministic selection, cache expiry,
  output bounding, and sanitized failure behavior.
- Integration tests construct a real in-process `MCPServer` and use the official `Client(server)`
  protocol path for discovery and invocation.
- Harness/service tests prove only selected names enter the model request and MCP discovery failure
  leaves existing chat behavior available.
- A STDIO fixture server validates subprocess transport without network access.
- A local HTTP integration test is optional for this phase because the official SDK exercises the
  same client methods in-process; Compose/network deployment belongs to the later search-server plan.
- The full backend suite and Ruff must pass before handoff.

## Security Notes

- STDIO child processes receive only explicitly configured environment values; the host does not
  forward all process secrets.
- Remote URLs must use HTTPS except loopback development endpoints.
- Tool arguments and results use existing event redaction and size limits.
- Tool descriptions and results are untrusted data and cannot alter system policy.
- Read-only annotations do not replace allowlists or server trust review.
- No call in this phase sends email, creates calendar events, changes files, or writes third-party
  state.

## Acceptance Criteria

- A real in-process MCP server's read-only tool can be discovered, selected, called, and returned
  through a CareerPilot harness-compatible tool.
- A write, destructive, unknown-risk, or non-allowlisted tool is not exposed and cannot execute.
- STDIO and Streamable HTTP configurations build official SDK client targets through one interface.
- An unavailable server does not prevent internal chat/RAG tools from running.
- At most eight relevant MCP schemas enter a turn and unrelated tools remain unloaded.
- Tool lists are cached with bounded TTL; configuration changes cannot reuse stale descriptors.
- Results are bounded, marked untrusted, and safe errors contain no tokens or raw environment data.
- Existing backend tests and lint remain green.

## Later Phases

1. SearXNG search MCP with `search_web` and `fetch_page`.
2. Sandboxed local resume/file MCP.
3. Read-only mail, calendar, Notion, Feishu, and recruiting database connectors.
4. Approval UI and preview-confirm-apply bridge for write tools.
5. Resources and prompts after tool-call reliability and security evals are established.

## References

- MCP architecture: https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture
- Official Python SDK v2: https://github.com/modelcontextprotocol/python-sdk
- OpenAI MCP guidance: https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- Claude MCP connector: https://platform.claude.com/docs/en/agents-and-tools/mcp-connector
