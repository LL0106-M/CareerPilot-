# CareerPilot Reliable Harness Design

## Intent

CareerPilot will remain a product-specific career companion agent while upgrading its existing
runtime into a reliable agent harness. The harness, rather than the model, must own execution
history, tool policy, recovery, deadlines, verification, and the boundary between verified output
and long-term learning.

The purpose is not to build a general agent framework. The purpose is to make CareerPilot's
career-context, memory, evidence, and user-authorized actions dependable under model mistakes,
provider timeouts, process crashes, duplicate requests, and long conversations.

## Goals

- Make one append-only session event log the authoritative record of every model-visible fact.
- Persist turn, step, assistant attempt, tool call, and tool result events before dependent work
  proceeds.
- Derive model history from committed session events rather than maintaining a second message
  history as an independent source of truth.
- Recover interrupted turns without replaying an external side effect as though it never happened.
- Enforce one end-to-end run deadline and propagate cancellation through context compilation,
  model calls, tool execution, verification, and learning.
- Expose live authenticated run events over SSE while preserving the existing synchronous chat API
  for compatibility.
- Turn verification into a completion gate with one bounded repair attempt for repairable failures.
- Prevent partial, failed, or unverified turns from updating long-term cognitive state.
- Preserve the existing owner-scoped Memory, RAG, Action Service, and frontend contracts wherever
  possible.

## Non-goals

- Replacing the application with DeepSeek Harness, LangGraph, DeepAgents, or another framework.
- Building an all-purpose plugin marketplace or multi-agent runtime.
- Adding user login or changing the current identity model in this phase.
- Adding autonomous external writes. Existing preview, confirmation, apply, and verification rules
  remain authoritative.
- Automatically retrying side-effecting tools.

## Anti-goals

- A second event log that cannot reconstruct the model-visible conversation.
- A checkpoint that records only status while claiming to support execution resumption.
- Silent context loss when compaction or persistence fails.
- Verification that produces warnings but cannot prevent completion or learning.
- Retrying an action when its outcome is unknown.
- Turning CareerPilot into a framework whose abstractions obscure product policy.

## Constraints

- Python remains `>=3.12,<3.13`; FastAPI, Pydantic, SQLite, and the current provider-neutral model
  contracts remain in use.
- Existing database files require additive, monotonic migrations; committed data is never rewritten
  destructively.
- The current `/v1/chat` response remains supported during migration.
- Every event and query remains scoped to the authenticated owner abstraction, even though this
  phase still obtains that owner from the anonymous cookie identity.
- External actions retain their current idempotency and explicit confirmation contracts.
- New behavior is developed test-first.

## Approaches Considered

### 1. Incremental event-sourced harness — selected

Keep the current Python application and public APIs, add a canonical session event store, project
messages from it, and migrate the runtime one boundary at a time. This gives CareerPilot the
reliability properties it needs without replacing its Memory, RAG, Action, and product layers.

Trade-off: the migration temporarily carries compatibility adapters, and the resulting harness is
purpose-built rather than a reusable ecosystem.

### 2. Full DeepSeek-style harness rewrite

Replace the runtime with a plugin tree, scoped services, typed event extension maps, reversible
lifecycle effects, and profile composition.

Trade-off: maximum extensibility, but disproportionate cost and architectural surface for a
single-product agent. It delays improvements users can observe and increases migration risk.

### 3. Adopt an external orchestration framework

Move the loop and persistence to an existing agent framework and adapt CareerPilot services as
tools or middleware.

Trade-off: faster access to generic features, but less control over memory admission, evidence
handling, action confirmation, and recovery semantics. It also creates framework coupling at the
product's most differentiated boundary.

## Architecture

### Canonical session log

`SqliteSessionEventStore` becomes the single durable source of truth. Each event has:

- `session_id`, `sequence`, `turn_id`, and optional `step`;
- an event type and schema version;
- a JSON payload;
- creation time;
- owner identity at the session header level;
- an idempotency key for externally submitted user messages.

Core event types are:

```text
turn.started
user.message
step.started
model.attempt
assistant.message
tool.requested
tool.result
step.completed
turn.completed
turn.failed
turn.cancelled
turn.interrupted
context.compaction.started
context.compaction.completed
context.compaction.failed
```

The event store accepts only contiguous sequences under a per-session write lease. SQLite
transactions provide the initial single-process lease implementation; an ownership/version field
prevents stale writers and leaves a future cross-process backend possible.

`derive_messages(session)` is a pure projection from committed events. The legacy message store is
retained only as a migration reader until existing sessions are imported or naturally expire.

### Turn durability and recovery

The runtime commits each model-visible event before deriving the next model request. A tool call is
recorded before dispatch, and its canonical outcome is recorded before another model step.

On startup or session resume, an open trailing turn is repaired deterministically:

- an open tool call receives an `unknown` tool result, never an automatic retry;
- an open step receives an interrupted completion;
- the turn closes as `turn.interrupted`;
- the next user request starts a new turn and sees the repaired history.

Side-effecting tool results use `succeeded`, `failed`, `denied`, `timed_out`, `cancelled`, or
`unknown`. `unknown` means the provider may have acted and requires user-visible reconciliation.

### Run budget and cancellation

Each run owns a `RunBudget` containing an absolute monotonic deadline and cancellation signal.
Stages receive the same budget and may claim only the remaining time. The initial default is 120
seconds, configurable through settings.

Cancellation is checked before and during awaitable operations. Model and tool adapters receive a
child timeout capped by the remaining run budget. Persistence cleanup and closing events run in a
short shielded finalization budget so cancellation cannot leave a falsely open turn.

No automatic retry is performed for tools. Read-only provider/model calls may receive at most one
retry when the failure is explicitly transient and enough run budget remains.

### Streaming transport

The current synchronous `/v1/chat` remains. A new run-oriented API adds:

```text
POST /v1/runs
GET  /v1/runs/{run_id}/events/stream
GET  /v1/runs/{run_id}
POST /v1/runs/{run_id}/cancel
```

`POST /v1/runs` creates the run and returns immediately. The SSE endpoint emits committed run and
session events in sequence order, supports `Last-Event-ID`, sends heartbeats, and verifies owner
scope before streaming. Reconnection reads from durable events rather than process-local queues.

### Verification and bounded repair

Verification becomes intent-aware. Every turn checks:

- a non-empty user-facing response;
- no unhandled or unknown tool outcome;
- citation integrity when evidence was available or external facts were asserted;
- support-mode constraints, including question count and prohibited tools;
- action claims against durable action receipts;
- task-specific completion criteria from the plan.

Repairable failures produce structured corrective context and permit one additional model attempt
inside the same turn and run budget. Safety violations, unknown action outcomes, exhausted budgets,
and persistence failures are not auto-repaired; they terminate as partial, blocked, or failed.

The verifier's result controls the runtime state. It is no longer informational metadata.

### Learning gate

Memory admission is separated from response delivery. Only `verified` turns may update durable
personal memory or enqueue Dreaming. A partial response may still be shown to the user, but it
cannot promote assistant-generated conclusions into cognitive state.

Explicit user memory commands may be admitted from the user's own message after deterministic
policy checks even when response verification fails; the admission record must cite the user
message event rather than the assistant response.

### Context accounting and compaction

The context budget covers the complete model request: stable system contract, dynamic context,
derived history, current turn, and tool schemas. Provider tokenizers may implement exact counting;
the existing estimator remains a conservative fallback.

Compaction is an event-log transaction with an explicit covered sequence range and source hash.
Tool request/result pairs cannot be split. Failure preserves the uncompressed history or terminates
with an explicit context-limit error; it never silently drops old turns.

The stable system contract is separated from a late dynamic context envelope containing intent,
memory, hypotheses, and retrieval policy. This improves provenance and permits better provider
prefix reuse without weakening the authority hierarchy.

### Tool execution contract

The first phase does not create a general plugin system, but it extends tool metadata with:

- risk class (`read`, `write_preview`, `external_effect`);
- timeout;
- idempotency requirement;
- retry policy (`never` or `transient_read_once`);
- result schema and sensitivity policy.

Tool outcomes are canonical structured objects. Policy denial, invalid input, timeout, cancellation,
provider failure, and unknown outcomes are distinct. The Action Service continues to own preview,
confirmation, apply, and receipt verification.

## Compatibility and Migration

1. Add new event tables and schema version without removing legacy session messages.
2. Dual-read old sessions through a compatibility projection; all new turns write canonical events.
3. Keep existing chat and run-query response models stable.
4. Introduce asynchronous run and SSE endpoints without forcing the frontend to migrate immediately.
5. After event projection has been exercised in production, remove legacy message writes in a
   separate migration.

## Failure Semantics

- Persistence failure before tool dispatch: the tool is not executed and the run fails.
- Persistence failure after an external effect: record an `unknown` receipt when possible, surface a
  reconciliation warning, and never retry automatically.
- Model timeout: close the attempt and turn with a typed timeout failure.
- Client disconnect: the run follows its submitted execution policy; initially it continues unless
  the user explicitly cancels it.
- SSE disconnect: no run cancellation; reconnection resumes from the durable event sequence.
- Verification failure: at most one repair attempt, then partial/blocked/failed with no learning.
- Compaction failure: preserve history and fail explicitly if the provider context limit cannot be
  met.

## Observability

Every run reports stage and total latency, model/tool usage, retry count, repair count, context token
composition, compaction decisions, verification criteria, and terminal reason. Sensitive tool
payloads are redacted before event persistence, not merely before API serialization.

## Testing Strategy

- Event-store contract tests for contiguous append, owner scope, write ownership, and replay.
- Runtime crash-boundary tests before dispatch, after dispatch, and after tool result.
- Recovery tests proving unknown external outcomes are not replayed.
- Budget and cancellation tests across context, model, tool, verification, and learning stages.
- SSE reconnect and owner-isolation tests.
- Verification red/green tests for citations, tool failures, support constraints, and action claims.
- Learning-gate tests proving partial and failed turns do not update cognitive state.
- Context-budget and compaction transaction tests, including failed summaries and tool pairs.
- Existing Harness, Agent, API, Memory, RAG, and Action tests remain regression gates.

## Delivery Slices

1. Canonical session event store, projection, lease, and interrupted-turn recovery.
2. Runtime integration with durable model/tool boundaries and canonical outcomes.
3. End-to-end run budget and cancellation propagation.
4. Intent-aware verification, one bounded repair attempt, and learning gate.
5. Asynchronous run creation and authenticated resumable SSE.
6. Full-request context accounting and transactional compaction.
7. Documentation, migration cleanup, and expanded evaluations.

Each slice must leave the synchronous chat path working and independently testable.

## Deferred User Authentication

User login is intentionally the next design project. The harness will depend only on an
`AuthenticatedPrincipal`/owner abstraction, so replacing the anonymous cookie with account-backed
identity will not require another runtime rewrite. Existing anonymous data migration and account
linking will be decided in that design.
