---
date: 2026-10-23
topic: personal-action-connector-mvp
---

# Personal Action Connector MVP Design

## Intent

CareerPilot is a companion-style Personal Agent: the user expresses a goal or idea, and the
agent may turn it into a real action without bypassing user control. This MVP adds a governed
backend boundary for Feishu, WPS, and NetEase Mail while making authorization state explicit.

## Product Decisions

- Use CareerPilot domain capabilities; do not expose raw MCP or provider commands to the agent.
- Every external write follows Preview -> Confirm -> Apply -> Verify.
- The API always reports whether a provider is configured and whether the current user granted
  each capability.
- Feishu includes document creation and calendar creation in the first connector pack.
- WPS includes cloud file/document creation in the first connector pack.
- NetEase Mail is mandatory but read-only in the MVP; sending mail is not registered.
- QQ Mail and WeChat are out of scope.
- External content is an observation, not long-term personal memory.

## Approaches Considered

1. Provider-specific routes and direct agent tools. Fast initially, but duplicates authorization
   logic and lets provider details leak into prompts.
2. A central capability registry, permission grants, and action service with provider adapters.
   Selected because authorization, confirmation, idempotency, and receipts remain consistent.
3. A general policy engine. Deferred because it adds deployment and rule-language complexity
   before the MVP has enough capabilities to justify it.

## Architecture

```text
Agent/API
  -> Capability Registry
  -> Permission Grant Store
  -> Action Service (preview/confirm/apply/verify)
  -> Connector Registry
       -> Feishu CLI
       -> WPS OpenAPI
       -> NetEase IMAP (read only)
```

SQLite stores owner-scoped grants, action previews, single-use confirmations, idempotency keys,
and non-sensitive receipts. Provider secrets remain in an injected credential/configuration
layer. The initial environment-backed resolver is explicitly for single-machine development;
it is not presented as multi-user production OAuth.

## MVP Capabilities

| Provider | Capability | Risk | Confirmation |
|---|---|---:|---|
| Feishu | `document.create` | L3 | every apply |
| Feishu | `calendar.create` | L3 | every apply |
| WPS | `document.create` | L3 | every apply |
| NetEase Mail | `email.search_recruiting` | L1 | grant required; no per-call confirmation |

Feishu task/message capabilities may be registered later, but are not part of this implementation.

## Authorization Contract

A provider status contains `configured`, `connection_state`, capability-level `grant_state`,
scope labels, and `last_used_at`. A grant is bound to `owner_id`, provider, capability, purpose,
and optional resource constraints. Revocation blocks new previews and applies immediately.

The backend never infers authorization from the presence of a token alone. Provider credentials
and an active CareerPilot grant are both required.

## Action Contract

`POST /v1/me/actions/preview` validates the capability and payload, stores a normalized immutable
preview, and returns a hash. `POST /v1/me/actions/{id}/confirm` issues a single-use confirmation
token bound to that hash. `POST /v1/me/actions/{id}/apply` requires the token and an idempotency
key. Repeated application with the same key returns the stored receipt; changed payloads require
a new preview.

Receipts use `completed|failed|unknown`, provider ID, opaque external reference, observations,
and a retryable flag. Verification is performed by the connector when supported; otherwise the
status cannot be `completed`.

## Connector Boundaries

### Feishu CLI

Run `lark-cli` as a subprocess with a fixed argv allowlist, JSON output, timeout, and user identity.
No shell command construction is permitted. `docs +create` creates documents; calendar creation
uses the CLI calendar command discovered from installed CLI help/schema. CLI authorization is
probed separately from the user's CareerPilot grant.

### WPS

Use an injected `httpx.AsyncClient`. The MVP creates an item beneath an explicitly configured
drive and parent with WPS OpenAPI. Bearer tokens are never logged or persisted in the action DB.
The returned file ID and link are reduced to an opaque receipt.

### NetEase Mail

Use IMAP4 over SSL with a configured account and client authorization code. Search only a bounded
recent window and return metadata required to identify recruiting messages: message ID hash,
sender, subject, and received date. Do not return bodies, attachments, or unrelated messages.

## Safety and Privacy

- Owner ID always comes from the signed HttpOnly cookie.
- Connector payload schemas reject unknown fields.
- No endpoint accepts raw provider tokens or passwords.
- Logs and receipts exclude document bodies, email bodies, credentials, and recipient lists.
- External provider data never enters MemOS automatically.
- Provider status and grants are visible and revocable.

## Non-goals

- Production multi-user OAuth/token vault.
- Email sending, replying, forwarding, or attachment download.
- Rich WPS document-body editing.
- Feishu messages, tasks, callbacks, or proactive scheduler.
- Cross-provider workflows and automatic writes.
- QQ Mail and WeChat.

## Acceptance Criteria

- An owner can list provider and per-capability authorization state.
- Revoked or missing grants block preview/apply before any connector call.
- A confirmed unchanged preview executes once and returns a verified receipt.
- Confirmation replay, payload drift, and duplicate idempotency cannot create duplicate effects.
- Feishu/WPS adapters produce exact provider calls in contract tests.
- NetEase adapter can find bounded recruiting-message metadata without exposing body content.
- Existing backend and frontend suites remain green.
