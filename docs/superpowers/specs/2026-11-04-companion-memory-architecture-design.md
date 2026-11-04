# CareerPilot Companion Memory Architecture

## Intent

CareerPilot needs memory that preserves relationship continuity without turning a vulnerable moment
into a permanent identity claim. The system must remember how the user wants to be accompanied,
retain important career history, show why something was remembered, and make correction or
forgetting immediate and trustworthy.

## Goals

- Separate current-turn context, user-protected promise memory, stable semantic memory, episodic
  experience, and inferred cognitive hypotheses.
- Make recall read-only; learning occurs only after a completed, persisted assistant turn.
- Prefer current user statements over historical memory and explicit memory over inference.
- Keep transient distress and negative self-judgment out of durable memory.
- Make every active memory visible, editable, pausable, resumable, and deletable by the user.
- Preserve evidence, revisions, owner scope, sensitivity rules, and retrieval auditability.
- Support exact/lexical recall now and optional dense or associative recall later.

## Non-goals

- MemOS is not an authoritative store and cannot bypass local admission or lifecycle rules.
- This phase does not implement a full Akasha-style plastic associative graph.
- The system does not infer diagnoses, personality labels, or career fit as confirmed facts.

## Memory layers

1. **Working context**: current message, recent complete turns, support mode, open loop. Never durable
   by default.
2. **Promise memory**: explicit "remember this", pinned messages, confirmed interaction preferences.
   Protected from automatic pruning.
3. **Semantic profile**: stable facts, preferences, goals, constraints, decisions, and capabilities.
   Automatic extraction remains candidate unless it is explicit and low-risk.
4. **Episodic memory**: time-scoped events, attempts, outcomes, and the user's own reflection. An
   episode cannot silently become a trait.
5. **Cognitive relations**: hypotheses, supporting and contradicting evidence, supersession, and
   open questions. Hypotheses stay visibly uncertain.

## Admission and learning

Only a successfully completed turn may enter admission. The deterministic policy admits explicit,
durable user-authored statements; it rejects transient distress, self-judgment, and broad incidental
phrases. Each candidate is classified, normalized, deduplicated, sensitivity-checked, and compared
for conflict. Multiple writes from one turn are atomic.

Explicit corrections replace only a specifically related record. Token overlap alone is not enough.
Sensitive upgrades create a candidate replacement; confirming it atomically activates the new
record and supersedes the old record.

## Retrieval

Retrieval first checks current intent, no-history instructions, purpose, scope, and sensitivity.
Eligible active records are ranked with lexical relevance, optional dense relevance, importance,
confidence, recency, and purpose. A future associative lane may add related episodes, but explicit
recall stays read-only and cannot change future ranking or learning state.

Memory usage is recorded only after a successful answer, against the concrete run/turn ID.

## User control

- "Do not use history this time" disables recall for the current turn only.
- Pause stops recall immediately without deleting provenance.
- Correction creates a new version/replacement and retires the specifically corrected value.
- Delete immediately removes the record from recall; index and relations follow the same lifecycle.
- The memory screen uses canonical API data, never demo data, and exposes source, status,
  sensitivity, update time, edit, pause/resume, confirm, and delete.

## Approaches considered

- Patch-only CRUD fixes: cheapest, but leaves memory as an untrustworthy keyword notebook.
- Layered governed memory (selected): combines user-protected memory, governed automatic facts,
  episodes, and future associative recall while fitting the existing service/store boundaries.
- Full Akasha graph replacement: strongest association mechanics but too large and opaque for the
  current MVP; retain as a future optional retrieval lane.

## MemOS decision

The canonical SQLite store remains authoritative. MemOS may be enabled later as a semantic proposal
or ranking provider only when evaluated recall quality justifies it. Its output must reconcile to a
local record ID or enter as a candidate, and local pause/delete/sensitivity decisions always win.

## Phase-one delivery

1. Fix transient-emotion admission, profile-update wording, correction targeting, sensitive
   replacement confirmation, and atomic multi-candidate writes.
2. Move usage recording to successful run completion with the run ID.
3. Connect the memory page to canonical APIs with real lifecycle controls.
4. Add regression tests for trust-critical behavior and API/UI integration.
