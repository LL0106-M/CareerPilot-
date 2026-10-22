# CareerPilot Harness Architecture

## 1. Decision

CareerPilot uses one user-facing agent on a product-specific harness. The harness is owned by
this repository and does not delegate its loop, session lifecycle, context assembly, tool policy,
or memory admission to DeepAgents or another orchestration framework.

This is deliberately not a general plugin platform. The product differentiator is the quality and
traceability of intent-aware context, personal memory, cognitive state, and career evidence.

## 2. Boundaries

```text
CareerPilot Agent System
├── Agent Definition
│   ├── identity and objectives
│   ├── support behavior
│   └── tool-selection and answer behavior
├── CareerPilot Harness
│   ├── runtime kernel
│   ├── intent-aware context compiler
│   ├── memory lifecycle
│   ├── RAG orchestration
│   ├── tool policy
│   └── session persistence
└── Product Application
    ├── API and authentication
    ├── product state
    └── user-facing views
```

The agent makes semantic decisions. The harness enforces invariants. MemOS is the personal-memory
backend, not the complete memory architecture. Career hypotheses, evidence relationships, tasks,
and permissions remain structured CareerPilot state.

## 3. Turn lifecycle

```text
user message
→ SupportPolicy resolves the initial interaction mode
→ CareerContextCompiler retrieves MemOS and cognitive state
→ PromptComposer produces attributed, bounded context
→ CareerPilotHarness loads durable session history
→ ModelGateway streams from the configured provider
→ ToolPolicy filters requested tools
→ ToolRegistry validates and executes an allowed call
→ the result is appended and the model continues
→ the final turn is persisted
→ MemoryLifecycle applies write admission and queues consolidation
```

The first implementation caps a turn at four model steps. A model cannot bypass the tool allowlist:
even a malformed or adversarial request for a hidden tool receives a structured forbidden result.

### 3.1 Runtime protocol

`CareerPilotHarness.stream()` is the canonical execution interface. It is an async generator of
provider-neutral `HarnessEvent` values. `run()` consumes that same stream and folds the terminal
event into `HarnessRunResult`, so non-streaming application code does not maintain a second loop.

```text
run.started
→ model.started
→ model.text_delta *
→ model.completed
→ [tool.requested → tool.started → tool.completed → model.started] *
→ run.completed | run.failed | run.cancelled
```

Every event carries `run_id`, `session_id`, monotonic `sequence`, `phase`, and `step`. Payloads are
JSON-compatible and do not expose LangChain or provider event classes. An API transport can map the
same stream to SSE or WebSocket, while an event store or trace collector can consume it directly.

`AgentRunState` enforces legal phase transitions:

```text
created → running → model ⇄ tools → completed
                       └───────→ failed / cancelled
```

Model messages and runtime events are deliberately different protocols. Messages form the context
sent to the model; events describe execution to product clients and operations systems.

## 4. Memory layers

| Layer | Owner | Purpose |
|---|---|---|
| Working context | Harness session | Current turn and recent conversation |
| Personal memory | MemOS adapter | Cross-session user facts, preferences and episodes |
| Cognitive state | CareerPilot SQLite store | Hypotheses, evidence and confidence |
| Product state | CareerPilot product store | Tasks, documents, permissions and UI state |
| Career knowledge | RAG store | Reusable, sourced external knowledge |

Memory retrieval happens before the first model request. The model may request additional governed
knowledge through a tool, but it cannot write directly to MemOS. Post-turn admission remains a
deterministic policy boundary; consolidation produces reviewable proposals.

## 5. Model boundary

`ModelGateway` accepts CareerPilot-owned messages and tool schemas and emits `ModelStreamEvent`
values. The initial provider adapter uses LangChain's chat-model transport, but provider chunks never
enter the runtime or application layer. Replacing that adapter with a direct OpenAI-compatible client
does not change the harness event contract.

## 6. Persistence and failure semantics

Session messages are append-only rows in SQLite and include assistant tool calls and tool results.
RAG, cognitive state, product state, and sessions use separate files because they have different
retention and migration requirements.

The runtime already exposes ordered streaming events, explicit phases, terminal failure events,
cooperative cancellation semantics, tool lifecycle events, accumulated usage, and a compatibility
collector for existing request/response callers.

Current limitations that must still be resolved before public production deployment:

- add per-session concurrency control and optimistic turn ownership;
- persist explicit turn/step events, not only reconstructed messages;
- expose the runtime stream through an authenticated SSE or WebSocket endpoint;
- add provider timeouts, bounded retry budgets, and idempotency keys for side-effecting tools;
- add token budgets, context compaction, repeated-action detection, and long-task checkpoints;
- replace keyword-only intent routing with an evaluated structured classifier;
- add Memory retrieval and write-admission evaluation datasets;
- derive user identity from authentication rather than request JSON.

## 7. Migration policy

Existing RAG and MemOS adapters remain behind stable ports. New work should depend on contracts under
`careerpilot.harness`, not on LangChain or provider response types. Historical implementation plans
may mention DeepAgents; they are retained as project history and are not current architecture.
