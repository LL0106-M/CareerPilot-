# Governed MemOS Memory Pipeline Design

## Intent

CareerPilot will replace keyword-to-record memory writes with a schema-driven, governed pipeline.
OpenViking is a design reference for session extraction, typed schemas, patch planning, and diff
auditing; it is not a runtime dependency. MemOS Cloud becomes the semantic memory data plane while
CareerPilot retains a compact local control ledger for owner scope, lifecycle, evidence, versions,
provider mapping, and safe deletion.

## Goals

- Prevent instructions, prompt injection, third-party claims, transient emotions, and unsupported
  inference from becoming active user memory.
- Extract typed, normalized claims with subject, authorship, evidence, durability, sensitivity, and
  confidence.
- Produce explicit `create | update | supersede | delete | noop` patch operations.
- Decide every proposal as `commit | pending | ignore | reject` using deterministic policy.
- Send only committed canonical claims to MemOS; never dual-write the raw completed turn.
- Treat MemOS search output as untrusted and gate it through local owner/status/provider mappings.
- Preserve user-visible CRUD and immediate local pause/delete semantics.
- Migrate current records idempotently, quarantine unsafe records, and reconcile provider mappings.

## Non-goals

- Installing or embedding OpenViking.
- Moving Session, RAG, Product, Journey, Task, Calendar, or Dreaming job state into MemOS.
- Letting MemOS grant permissions or define canonical lifecycle state.
- Hard-deleting the existing database during rollout.
- Automatically activating AI or Dreaming inference without user confirmation.

## Approaches

1. Add filters around the existing marker extractor. Fast but keeps keyword matching as the core.
2. Build a schema-driven governed patch pipeline and use MemOS as the data plane. Selected because
   it fixes the write model while fitting existing service boundaries.
3. Send every completed turn directly to MemOS. Smallest code surface but insufficiently auditable
   and gives CareerPilot too little control over correction, deletion, and sensitive content.

## Memory model

The cognitive class and business tag are separate axes. Cognitive classes are `episodic`,
`semantic`, `procedural`, and `prospective`; working context remains outside long-term memory.
Business tags reuse the existing `fact`, `preference`, `goal`, `constraint`, `idea`, `experience`,
`decision`, and `hypothesis` API contract.

Each extracted claim contains:

- canonical content;
- business type and cognitive class;
- subject `self | peer | organization | unknown`;
- authorship `user_explicit | user_confirmed | agent_inferred | system_observed | imported`;
- evidence message IDs and bounded excerpts;
- durability `transient | episodic | durable`;
- sensitivity `normal | private | sensitive`;
- confidence `low | medium | high`;
- optional correction and target hints.

## Write pipeline

```text
completed persisted turn
  -> deterministic safety prefilter
  -> schema claim extractor
  -> patch planner against active local projection
  -> deterministic admission gate
  -> atomic local control-ledger transaction
  -> committed canonical claims only to MemOS
  -> provider mapping/retry audit
```

The safety prefilter rejects or strips executable instructions, credential-like material, requests
to reveal system prompts or other users' data, and claims whose subject is not the current user.
It may skip extraction entirely for ordinary turns without durable information, but marker presence
alone can never authorize a write.

The extractor is behind a protocol. Production uses the existing reasoning model and validated
structured JSON. Tests and offline fallback use a deterministic extractor. Model output is a
proposal and never writes storage directly.

Admission decisions:

- `commit`: explicit current-user, durable, normal/private, safe claim with sufficient evidence.
- `pending`: inferred, ambiguous, sensitive, low-confidence, or conflicting claim.
- `ignore`: temporary, trivial, irrelevant, or non-user content.
- `reject`: injection, credential, cross-owner, prohibited diagnostic/personality claim, or invalid
  evidence.

## Patch and lifecycle semantics

Patch operations are `create`, `update`, `supersede`, `delete`, and `noop`. Existing user-visible
states remain `candidate`, `active`, `paused`, `superseded`, and `deleted` for API compatibility.
Every applied or skipped patch receives a stable reason code and audit row. Corrections create a
new version or replacement; they never overwrite unrelated memories selected by token overlap.

## Local control ledger

SQLite remains the authority for owner, status, sensitivity, confirmation, evidence, revision,
usage, and audit. The current `memory_records.content` becomes a bounded local display/cache
projection so the management API works during MemOS outages; vectors and semantic ranking are no
longer authoritative locally.

New provider state records:

- local memory ID and provider name;
- provider memory ID when reconciled;
- sync state `pending | synced | failed | delete_pending | deleted`;
- attempt count, bounded error code, timestamps, and canonical content hash.

New patch audit records preserve the source turn, proposed operation, admission decision, reason
code, and resulting local memory ID without storing secrets.

## MemOS data plane

Committed claims are written with a stable `user_id`, a deterministic provider conversation ID,
and metadata containing the local memory ID, type, status, scene, and schema version. The payload
contains the canonical claim and a minimal acknowledgement, not the raw chat transcript.

Because `addMessage` does not document a synchronous stable memory ID, the local row first enters
`pending`. Reconciliation searches or lists memories using local ID metadata and stores the returned
provider ID. Until reconciliation succeeds, local retrieval remains the safe fallback.

Deletion is local-first: local status immediately becomes deleted, provider sync becomes
`delete_pending`, and no cloud result can re-enter context while remote deletion is retried.

## Retrieval

The context compiler asks MemOS first when enabled. Returned facts must match the authenticated
owner and CareerPilot metadata, map to a locally active record, and pass sensitivity/purpose gates.
Unmapped results never enter the prompt; they may be staged for reconciliation. If MemOS is
unavailable or produces no governed results, active local projections provide deterministic
fallback. Current user statements always outrank historical memory.

## Migration

Migration is idempotent and non-destructive:

1. classify existing active records through the new admission gate;
2. quarantine injection-like and invalid-subject records as candidates/paused records;
3. collapse exact duplicates only within the same owner;
4. create provider-sync entries for safe active memories;
5. write/reconcile safe claims to MemOS;
6. emit a report with counts and reason codes;
7. retain revisions and evidence; never delete legacy rows automatically.

## Failure behavior

- Extraction failure: no write; response remains successful.
- Local transaction failure: do not call MemOS.
- MemOS write failure: local state remains valid and retryable.
- MemOS search failure: use governed local fallback.
- Reconciliation ambiguity: keep provider mapping pending and exclude the cloud result.
- Provider deletion failure: local tombstone continues blocking recall.

## Evaluation

Required suites cover admission precision, injection rejection, subject attribution, transient
emotion handling, sensitive confirmation, duplicate/conflict behavior, MemOS payload minimization,
provider failure, mapped-only recall, deletion consistency, migration idempotency, and owner
isolation. Existing Memory, Agent, API, Dreaming, RAG, and frontend contracts must remain green.

