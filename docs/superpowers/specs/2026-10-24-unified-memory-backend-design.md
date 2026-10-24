# Unified Memory Backend Design

## Intent

CareerPilot needs one backend memory contract before the frontend is rebuilt. Today, session
history, MemOS facts/preferences, Dreaming hypotheses, and ProductStore demo data are separate
systems. The new backend makes a local owner-scoped SQLite store authoritative, while keeping
MemOS behind an optional auxiliary interface for semantic extraction and retrieval experiments.

The product outcome is that a user can see, confirm, correct, pause, resume, and delete every
memory that may affect the Agent. The Agent can use only active records, and every use is
explainable.

## Goals

- Provide one canonical model for facts, preferences, goals, constraints, ideas, experiences,
  decisions, and hypotheses.
- Expose stable owner-scoped APIs for a future unified frontend.
- Separate proposed memories from active memories.
- Record provenance, evidence, revisions, lifecycle state, and downstream usage.
- Make memory retrieval deterministic, privacy-aware, and resilient without MemOS.
- Preserve conversation Session storage as a separate short-term concern.
- Fold Dreaming hypotheses into the same memory lifecycle without presenting them as facts.
- Preserve small user ideas as first-class, owner-scoped records that can mature into actions
  without being mistaken for facts, preferences, or granted action permissions.
- Produce a user-visible daily Dreaming review from the same evidence window used for background
  consolidation, while keeping that review separate from authoritative memory changes.
- Keep long conversations coherent through bounded context compaction without deleting the exact
  Session log or silently promoting a compaction summary into long-term memory.

## Non-goals

- Rebuilding the frontend in this phase.
- Building a graph database or a general knowledge graph.
- Automatically turning memories into external writes or granting action permissions.
- Importing fake ProductStore seed data as real user memories.
- Requiring MemOS for core CRUD, retrieval, or Agent operation.
- Solving cross-device encrypted synchronization in the MVP.
- Building the Idea Inbox, Daily Review, or context-health frontend in this phase.

## Selected approach

Three approaches were considered:

1. **MemOS as the source of truth.** Fastest, but lifecycle, audit, versioning, and user control
   remain constrained by a provider API.
2. **SQLite only.** Simple and private, but discards the existing semantic provider investment.
3. **SQLite authority with MemOS auxiliary capabilities.** Selected. SQLite owns all records and
   state transitions. MemOS may propose or rank candidates, but its output never becomes active
   or reaches the Agent without a canonical local record.

## System boundaries

```text
Conversation Session (existing SQLite)
        │ current turn
        ▼
Memory admission pipeline ──▶ candidate/active MemoryRecord
        │                              │
        │ optional proposal            │ authoritative query
        ▼                              ▼
SemanticMemoryProvider (MemOS)     MemoryService
                                       │
              ┌────────────────────────┼─────────────────────┐
              ▼                        ▼                     ▼
        MemoryStore              MemoryEvidence        MemoryUsage
          SQLite                    SQLite                SQLite
              │
              ▼
      CareerContextCompiler ──▶ Agent prompt
```

The existing `SqliteSessionStore` remains the exact conversational log. It is not merged into the
long-term memory database. RAG remains external knowledge and is never copied into personal
memory without an explicit memory proposal.

## Canonical domain model

### MemoryRecord

Required fields:

- `id`: UUID string.
- `owner_id`: authenticated owner; never accepted from request bodies.
- `type`: `fact | preference | goal | constraint | idea | experience | decision | hypothesis`.
- `content`: normalized user-readable statement.
- `status`: `candidate | active | paused | superseded | deleted`.
- `sensitivity`: `normal | private | sensitive`.
- `origin`: `user_explicit | agent_extracted | dreaming | imported`.
- `source_type`: `conversation | manual | integration | dreaming | migration`.
- `source_reference`: optional opaque reference to a conversation, integration item, or job.
- `confidence`: `low | medium | high`.
- `importance`: integer `1..5`, default `3`.
- `version`: optimistic-lock integer starting at `1`.
- `created_at`, `updated_at`, `last_used_at`, optional `expires_at`, optional `deleted_at`.

The content is not physically destroyed by the ordinary DELETE endpoint; it is soft-deleted and
excluded from all retrieval. A later privacy-erasure operation may hard-delete it and its evidence.

### MemoryEvidence

- `id`, `memory_id`, `owner_id`.
- `kind`: `user_statement | prior_memory | action_result | integration_item`.
- `source_reference` and a bounded `excerpt`.
- `created_at`.

Evidence is data, never executable instruction. Sensitive external content must be reduced to a
bounded excerpt or opaque reference.

### MemoryUsage

- `id`, `memory_id`, `owner_id`, `turn_id`.
- `usage_type`: `answer_context | retrieval_filter | action_suggestion | action_preview |
  goal_update | conflict_detected`.
- optional `result_reference`, `created_at`.

Usage is append-only. Updating `last_used_at` and inserting the usage row happen in one
transaction.

### MemoryRelation

- `source_memory_id`, `target_memory_id`, `owner_id`.
- `relation_type`: `supersedes | derived_from | supports | contradicts`.

MVP relations are limited to lifecycle and evidence reasoning. Idea-to-goal and goal-to-action
relations use these IDs later but do not execute actions.

### MemoryRevision and MemoryAuditEvent

Updates preserve immutable history. `memory_records` is the current projection;
`memory_revisions` stores the complete prior and new user-visible values for every version.
`memory_audit_events` is append-only and records operation, actor kind, record ID, version, and
timestamp without credentials or raw integration payloads. Create, update, lifecycle transition,
usage, migration, and provider-degradation events are auditable.

### IdeaItem

An idea is not only a `MemoryRecord(type=idea)`. The memory record preserves the original meaning,
provenance, sensitivity, authorization, and retrieval lifecycle. A linked `IdeaItem` stores the
product workflow that may change as the thought develops:

- `id`, `owner_id`, `memory_id` and `title`.
- `stage`: `captured | incubating | actionable | acted | validated | archived`.
- optional `related_goal_memory_id`, `next_step`, and `action_reference`.
- `version`, `created_at`, `updated_at`, and optional `last_reviewed_at`.

The raw wording stays in the linked MemoryRecord. IdeaItem never grants permission to call a tool.
Turning an idea into a task, calendar event, Feishu/WPS document, research run, or message always
uses the existing Preview/Confirm/Apply/Verify action boundary.

An explicit user command to save an idea follows the current memory grant. When the Agent merely
detects idea-like language, it creates a candidate only if the configured memory grant permits
candidate capture, and returns a visible storage receipt. Without that grant it may return an
ephemeral suggestion but must not persist the content. Integration-derived and sensitive ideas
always remain candidates until confirmed.

## Storage

Create `SqliteUnifiedMemoryStore` in the configured `CAREERPILOT_MEMORY_DB_PATH`. Tables are
owner-scoped and indexed by owner/status/type/update time. All read and write queries include
`owner_id`.

The store owns transactions, optimistic version checks, valid transitions, evidence, relations,
and usage. It does not decide whether content deserves admission.

`idea_items` lives in the same authoritative database and has a foreign key to
`memory_records(owner_id, id)`. Creating an idea and its canonical memory, appending their audit
events, and recording the storage authorization snapshot happen in one transaction. Owner scope
is required on both sides of every join.

Valid lifecycle transitions:

```text
candidate -> active | deleted
active    -> paused | superseded | deleted
paused    -> active | superseded | deleted
```

`superseded` and `deleted` are terminal in the ordinary API. An ordinary update increments the
same record's version and appends an immutable revision. A semantic contradiction creates a new
candidate and a `contradicts` relation; it does not silently overwrite an active record.

If an edit raises sensitivity to `sensitive`, the active record is not mutated in place. The
service creates a candidate replacement linked by `supersedes`; the old active record remains in
effect until the replacement is explicitly confirmed, at which point the transition is atomic.

## Service layer

`MemoryService` is the only API and Agent-facing boundary. It provides:

- `create_explicit(...) -> MemoryRecord`: user-authored records start active unless sensitive.
- `propose(...) -> MemoryRecord`: Agent, Dreaming, integrations, and imports start candidate.
- `list(...)`, `get(...)`.
- `update(..., expected_version)`: optimistic update; content changes retain provenance.
- `confirm(...)`, `pause(...)`, `resume(...)`, `delete(...)`.
- `search_context(owner_id, query, intent, limit) -> MemoryContextBundle`.
- `record_usage(...)`.

`IdeaService` is a narrow facade over the same store and transaction boundary. It provides:

- `capture_explicit(...) -> IdeaItem`: stores a user-requested idea under an active authorized
  memory record, or a candidate when sensitivity requires confirmation.
- `propose(...) -> IdeaItem`: creates an Agent/Dreaming/integration candidate only when candidate
  capture is authorized.
- `list(...)`, `get(...)`, and `update_stage(..., expected_version)`.
- `set_next_step(...)` and `link_action(...)`; linking records a reference but never executes it.
- `list_for_daily_review(owner_id, local_day)`.

Idea titles and next steps are projections. Editing them does not rewrite the user's original
statement. Editing the original idea content goes through `MemoryService.update` and revisioning.

`search_context` requires a `MemoryQueryPurpose` of `companion | planning | review |
action_preview`. Candidate hypotheses are never returned by ordinary search. A separate
`search_review_context` path may include them only when the intent interpreter selects
`INTERVIEW_REVIEW` or the user explicitly asks to review/reflect. Sensitive active records are
excluded from automatic context and are eligible only when the current message explicitly asks
the Agent to recall or use personal memory. They are always excluded from automatic
`action_preview` filters.

Only active, non-expired records are eligible for Agent context. Paused, candidate, superseded,
and deleted records remain visible in management APIs but never enter the prompt.

Search is local and deterministic in the MVP: normalized substring/token matching plus type,
importance, confidence, and recency ranking. It must work without network access. The result
contains record IDs so later usage is attributable.

## Admission pipeline

After a completed Agent turn:

1. `MemoryAdmissionPolicy` decides whether extraction is warranted.
2. `MemoryExtractor` returns zero or more typed proposals with evidence.
3. `MemoryService` normalizes content and checks exact/near duplicate active records.
4. Exact duplicates add evidence without creating another record.
5. Potential contradictions create candidates linked with `contradicts`.
6. User-explicit normal/private statements may become active; agent-extracted, Dreaming,
   integration-derived, and all sensitive proposals remain candidate.

The current marker policy becomes the first `MemoryAdmissionPolicy`; it is not the data store.
Extraction is behind a protocol so a deterministic extractor can ship first and an LLM extractor
can be added without changing APIs. Automatic post-turn work is placed on a durable
`memory_admission_jobs` queue after the completed turn has been persisted. Chat does not wait for
extraction. Jobs retry at most three times and record a bounded failure audit event; failure never
changes the already-produced response. Explicit user creation through the memory API is
synchronous.

## MemOS auxiliary role

Introduce `SemanticMemoryProvider` as an optional adapter. It may:

- ingest a completed turn for provider-side extraction;
- return semantic candidate text for reconciliation;
- rank canonical local records when a reliable local-ID mapping exists.

Provider results are untrusted proposals. They cannot be injected directly into the prompt and
cannot change canonical status. If no mapping exists, a result is staged as a local candidate with
`origin=imported`, never treated as active memory.

In this backend phase the working MemOS adapter is limited to bounded turn ingestion and health
state. Reconciliation, provider-to-local ID mapping, and provider reranking are deliberately
deferred until the provider can return stable local correlations. MemOS search results are not
used by Agent context in this phase. Provider degradation is stored in bounded
`memory_provider_events`; core CRUD and local retrieval continue and chat never fails because of
the provider.

## Dreaming integration

`dreaming_jobs` remains a durable queue. `career_hypotheses` is replaced by canonical
`MemoryRecord(type=hypothesis, status=candidate, origin=dreaming)` plus evidence and relations.
The processor keeps its three-attempt behavior.

Existing cognitive hypotheses are migrated idempotently from `career_hypotheses` in the configured
local memory database on store initialization. Their confidence becomes the record confidence;
supporting and contradicting IDs become evidence/relations; open questions are retained in a
bounded `metadata_json` field. A migration ledger prevents duplicate imports. Dreaming candidates
become active only after user confirmation.

Dreaming has two outputs from one immutable evidence window:

1. **DailyReview projection for the user.** It contains the day's minimum wins, new idea sparks,
   blockers, open loops, and one optional low-cost next step. It is a rebuildable read model, not a
   new memory category. The user may edit it; an edit appends a feedback event rather than
   rewriting its source events.
2. **MemoryPatch candidates for the system.** These deduplicate, connect, promote, demote, or
   expire memories and ideas. High-impact changes, inferred patterns, sensitive content, and
   contradictions require confirmation.

For ideas, the worker may merge exact duplicates, connect related records, mark an untouched idea
as incubating, or propose a next step. It may not silently mark an idea acted/validated, create an
external action, or turn an observation into a stable user trait.

The worker follows a shadow-output pattern inspired by Claude Dreams: it reads the current
canonical snapshot and selected Session transcripts, writes a separate run output and deterministic
diff, validates provenance and authorization, and only then atomically applies whitelisted patches.
The input snapshot is never mutated during analysis, and every applied patch is reversible.

Daily scheduling is based on the user's configured timezone. Event thresholds, career milestones,
and manual review may trigger additional runs, but only one run per owner may be active. A failed
run leaves the previous DailyReview and canonical memories unchanged.

## Context lifecycle and compaction

Context compaction is a foreground Harness responsibility, not a Dreaming responsibility and not
a MemoryRecord type. The exact `SqliteSessionStore` transcript remains append-only and recoverable.
The model request is assembled from:

1. fixed system, policy, permission, and pending-action state;
2. a structured continuation summary covering older completed turns;
3. the most recent complete turns verbatim;
4. current-turn content and unresolved tool-call pairs;
5. purpose-scoped Memory/Idea retrieval and governed RAG evidence.

`ContextWindowManager` first clears bulky re-fetchable historical tool results, then compacts only
when an estimated-token soft limit is exceeded. Compaction never splits a tool call/result pair and
never removes the current user message, pending confirmations, permission state, or recent turns.
The continuation summary preserves current goal, confirmed decisions, constraints, completed work,
failed approaches, open loops, referenced artifact IDs, and the next expected action. It is stored
in `session_compactions` with `session_id`, covered sequence range, summary schema version, source
hash, timestamps, and model metadata.

Before replacing old turns in the active model context, a pre-compaction flush may submit bounded
memory and Idea candidates through the normal admission and authorization pipeline. The summary
itself never becomes long-term memory. If compaction fails or its source hash is stale, the Harness
uses the last valid checkpoint plus a bounded recent window and does not invent a replacement.

Very long autonomous tasks may later use a clean context reset plus a structured handoff artifact.
That is an evolution path, not required for the first compaction MVP.

## ProductStore integration

`ProductStore` continues to own Journey tasks during this phase. Its `memories`, `hypotheses`, and
`dreaming_insights` tables stop being authoritative and are not seeded into canonical memory.
The dashboard endpoint composes Journey state from ProductStore with memory and hypotheses from
`MemoryService`. Compatibility response fields remain until the frontend migration is complete.

## HTTP API

All endpoints derive `owner_id` from the existing signed HttpOnly cookie.

- `GET /v1/me/memories`: filters `type`, `status`, `query`, cursor, and bounded limit.
- `POST /v1/me/memories`: explicit user creation; request has no owner field.
- `GET /v1/me/memories/{id}`.
- `PATCH /v1/me/memories/{id}`: requires `expected_version`.
- `POST /v1/me/memories/{id}/confirm`.
- `POST /v1/me/memories/{id}/pause`.
- `POST /v1/me/memories/{id}/resume`.
- `DELETE /v1/me/memories/{id}`: soft delete.
- `GET /v1/me/memory-candidates`.
- `GET /v1/me/memory-activity`: recent usage records with memory summaries.
- `GET /v1/me/ideas`: filters stage, query, related goal, cursor, and bounded limit.
- `POST /v1/me/ideas`: explicitly capture an idea; response includes storage authorization and
  canonical memory status.
- `GET /v1/me/ideas/{id}`.
- `PATCH /v1/me/ideas/{id}`: updates projection fields with `expected_version`.
- `POST /v1/me/ideas/{id}/stage`: performs a validated stage transition.
- `POST /v1/me/ideas/{id}/action-link`: records an already governed action reference.
- `GET /v1/me/daily-reviews` and `GET /v1/me/daily-reviews/{local_date}`.

Create accepts only `type`, `content`, optional `sensitivity`, `importance`, and `expires_at`.
The server fixes origin to `user_explicit`, source type to `manual`, and confidence to `high`.
PATCH accepts `content`, `type`, `sensitivity`, `confidence`, `importance`, `expires_at`, and a
required `expected_version`; it cannot alter owner, origin, source, lifecycle status, or audit
fields. Lifecycle status changes only through the dedicated endpoints.

Invalid transitions and version conflicts return `409`; cross-owner or missing records return
`404`; invalid fields return `422`. Responses expose provenance, lifecycle, version, and
`last_used_at`, but never provider credentials or raw sensitive integration payloads.

## Agent integration

`CareerContextCompiler` calls `MemoryService.search_context` instead of directly querying MemOS
and the old cognitive table. Returned records are rendered in separate prompt sections:

- confirmed facts/preferences/goals/constraints/experiences/decisions/ideas;
- confirmed or candidate hypotheses, explicitly labeled by status and confidence.

For the MVP, only active records enter normal context. Candidate hypotheses may enter the
hypothesis section only through `search_review_context` under the explicit review rules above;
ordinary chat excludes them.
Every included record produces `MemoryUsage(usage_type=answer_context)` after the turn completes.

Memory can shape answers, retrieval filters, and action previews. It cannot grant permissions or
apply an external action.

## Privacy and safety

- Owner scope is mandatory at every persistence boundary.
- Integration-derived content always starts candidate.
- Sensitive content always requires explicit confirmation.
- Pausing is immediate and prevents retrieval.
- Soft deletion is immediate for retrieval; hard erasure is a separate future operation.
- Memory content is escaped and labeled untrusted before prompt insertion.
- Sensitivity is the maximum of client declaration, deterministic privacy policy, and extractor
  output; callers may raise sensitivity but cannot lower a policy-detected classification.
- Audit records contain operation metadata, not secrets or full external payloads.
- MemOS availability and authorization are separately visible; disabling it leaves local memory
  functional.

## Migration and compatibility

1. Create canonical tables without deleting current tables.
2. Idempotently import existing `career_hypotheses` as candidates.
3. Do not import ProductStore demo seeds.
4. Switch Agent reads and writes to `MemoryService`.
5. Compose dashboard memory fields from canonical records.
6. Keep legacy MemOS reads disabled for Agent context unless reconciled into canonical records.
7. Remove legacy tables only after the new frontend no longer consumes them.

## Testing strategy

- Store tests: owner isolation, transitions, optimistic concurrency, soft deletion, expiry,
  migration, evidence and usage transactions.
- Service tests: explicit versus proposed admission, sensitive confirmation, duplicates,
  contradictions, retrieval eligibility and ranking.
- API tests: signed-owner isolation, filters, validation, lifecycle endpoints, conflicts.
- Agent tests: only active records enter prompts; paused/deleted/candidate records do not; usage is
  recorded; memory failure degrades safely.
- Provider tests: MemOS failure cannot break local CRUD or chat; provider output remains candidate.
- Idea tests: authorization-aware capture, owner isolation, projection/version consistency,
  duplicate evidence, valid stage transitions, and no tool execution from an Idea mutation.
- Dreaming tests: timezone-bounded evidence, dual outputs, source traceability, shadow diff,
  rollback, and unchanged canonical state after failure.
- Compaction tests: token trigger, recent-turn preservation, atomic tool pairs, protected state,
  stale-source rejection, deterministic fallback, and no automatic long-term write of summaries.

## Delivery boundary

This backend phase is complete when the stable APIs operate on canonical SQLite records, Agent
context and Dreaming use the same service, ProductStore is no longer authoritative for memories,
Idea capture and daily Dreaming projections are queryable, long conversations use bounded
compaction, and the existing full backend and frontend suites remain green. The Idea Inbox and
Daily Review frontend start only after this contract is committed.
