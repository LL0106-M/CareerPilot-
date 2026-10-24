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

## Non-goals

- Rebuilding the frontend in this phase.
- Building a graph database or a general knowledge graph.
- Automatically turning memories into external writes or granting action permissions.
- Importing fake ProductStore seed data as real user memories.
- Requiring MemOS for core CRUD, retrieval, or Agent operation.
- Solving cross-device encrypted synchronization in the MVP.

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

## Storage

Create `SqliteUnifiedMemoryStore` in the configured `CAREERPILOT_MEMORY_DB_PATH`. Tables are
owner-scoped and indexed by owner/status/type/update time. All read and write queries include
`owner_id`.

The store owns transactions, optimistic version checks, valid transitions, evidence, relations,
and usage. It does not decide whether content deserves admission.

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

## Delivery boundary

This backend phase is complete when the stable APIs operate on canonical SQLite records, Agent
context and Dreaming use the same service, ProductStore is no longer authoritative for memories,
and the existing full backend and frontend suites remain green. The frontend redesign starts only
after this contract is committed.
