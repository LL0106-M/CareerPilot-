# Personal Action Connector MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a governed backend MVP for visible authorization and safe Feishu, WPS, and NetEase Mail capabilities.

**Architecture:** A provider-neutral capability registry and SQLite action store sit between the Agent/API and connector adapters. All writes use preview-confirm-apply-verify; NetEase Mail remains a bounded read-only connector.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, httpx, stdlib subprocess/imaplib, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-personal-action-connector-mvp-design.md`

## Global Constraints

- Never store or return provider secrets.
- Never expose raw MCP/CLI commands to the model.
- All provider writes require a current grant and single-use confirmation.
- NetEase Mail is read-only and returns metadata only.
- Owner identity comes only from the server-side identity dependency.
- QQ Mail and WeChat remain out of scope.

## Review Focus

- A revoked grant between confirmation and apply must prevent connector execution.
- Reusing a confirmation token must not repeat an external side effect.
- Reusing an idempotency key with different content must be rejected.
- Provider timeout after an unknown outcome must return `unknown`, never `completed`.
- Email search must remain bounded and never return message bodies or attachments.

---

### Task 1: Capability Registry and Permission Store

**Files:**
- Create: `src/careerpilot/actions/models.py`
- Create: `src/careerpilot/actions/registry.py`
- Create: `src/careerpilot/actions/store.py`
- Test: `tests/actions/test_registry.py`
- Test: `tests/actions/test_store.py`

**Interfaces:**
- Produces: `CapabilityDefinition`, `ProviderDefinition`, `CapabilityRegistry`.
- Produces: `SqliteActionStore.grant()`, `revoke()`, `list_authorization()`, and grant lookup.

- [ ] Write failing tests for the fixed MVP capability catalog and owner-scoped grants.
- [ ] Run focused tests and verify failures are caused by missing action modules.
- [ ] Implement immutable models, the fixed registry, and SQLite grant persistence.
- [ ] Test that revoked grants are not usable and another owner cannot observe them.
- [ ] Run focused tests and Ruff.

### Task 2: Preview, Confirmation, Idempotency, and Receipts

**Files:**
- Create: `src/careerpilot/actions/service.py`
- Modify: `src/careerpilot/actions/store.py`
- Test: `tests/actions/test_service.py`

**Interfaces:**
- Consumes: `CapabilityRegistry` and `SqliteActionStore` from Task 1.
- Produces: `ActionService.preview()`, `confirm()`, and async `apply()`.
- Produces: `Connector` protocol with `probe()`, `execute()`, and `verify()`.

- [ ] Write failing tests for missing grants, normalized preview hashes, confirmation replay,
      payload drift, revocation after confirmation, and idempotent stored receipts.
- [ ] Run tests and confirm each failure reflects missing behavior.
- [ ] Implement the smallest state machine that satisfies the tests.
- [ ] Add timeout/unknown-outcome handling without automatic duplicate retry.
- [ ] Run focused tests and Ruff.

### Task 3: Provider Connectors

**Files:**
- Create: `src/careerpilot/connectors/base.py`
- Create: `src/careerpilot/connectors/feishu_cli.py`
- Create: `src/careerpilot/connectors/wps.py`
- Create: `src/careerpilot/connectors/netease_mail.py`
- Test: `tests/connectors/test_feishu_cli.py`
- Test: `tests/connectors/test_wps.py`
- Test: `tests/connectors/test_netease_mail.py`

**Interfaces:**
- Implements the Task 2 `Connector` protocol.
- Produces `ConnectorRegistry.get(provider_id)`.

- [ ] Write failing Feishu tests asserting fixed argv construction, JSON parsing, timeout mapping,
      and no shell execution.
- [ ] Implement Feishu document creation and calendar creation adapters.
- [ ] Write failing WPS tests using `httpx.MockTransport` for exact path, auth header, payload,
      response parsing, and provider errors.
- [ ] Implement WPS document creation.
- [ ] Write failing NetEase tests against an injected IMAP session for SSL login, bounded search,
      recruiting filters, metadata-only output, and logout.
- [ ] Implement the read-only NetEase adapter.
- [ ] Run connector tests and Ruff.

### Task 4: API, Settings, and Agent-facing Domain Tools

**Files:**
- Modify: `src/careerpilot/config.py`
- Modify: `.env.example`
- Create: `src/careerpilot/actions/tool.py`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/app.py`
- Test: `tests/api/test_actions.py`
- Test: `tests/actions/test_tool.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: `GET /v1/me/integrations`, grant/revoke routes, and preview/confirm/apply routes.
- Produces: agent tools for authorization status and action preview only; apply remains an API
  confirmation boundary.

- [ ] Write failing API tests for owner isolation, visible authorization, grant/revoke, preview,
      confirm, apply, and error mapping.
- [ ] Add secret configuration fields and safe connector construction.
- [ ] Implement routes and Pydantic request/response models with unknown-field rejection.
- [ ] Add agent-facing status/preview tools without exposing apply or raw connectors.
- [ ] Run API, tool, configuration, and existing agent tests.

### Task 5: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Documents local-only credential configuration and the production OAuth/token-vault boundary.

- [ ] Document capabilities, authorization visibility, preview-confirm-apply flow, and local setup.
- [ ] Run the full backend test suite with the required pytest plugin configuration.
- [ ] Run `ruff check .` and `git diff --check`.
- [ ] Run frontend tests and production build to catch shared schema regressions.
- [ ] Inspect the final diff for secrets and confirm the worktree is clean after commit.
