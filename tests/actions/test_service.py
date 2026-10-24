import asyncio
from typing import Any

import pytest

from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.service import (
    ActionService,
    ConfirmationError,
    ConnectorError,
    ConnectorOutcome,
    GrantRequiredError,
    IdempotencyConflictError,
    ResourceConstraintError,
)
from careerpilot.actions.store import SqliteActionStore


class RecordingConnector:
    def __init__(self, *, verified: bool = True) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.verified = verified

    async def probe(self) -> bool:
        return True

    async def execute(self, capability: str, payload: dict[str, Any]) -> ConnectorOutcome:
        self.calls.append((capability, payload))
        return ConnectorOutcome(external_reference="external-1", observations=("created",))

    async def verify(self, outcome: ConnectorOutcome) -> bool:
        return self.verified


class TimingOutConnector(RecordingConnector):
    async def execute(self, capability: str, payload: dict[str, Any]) -> ConnectorOutcome:
        self.calls.append((capability, payload))
        raise TimeoutError("provider outcome is uncertain")


class FailingConnector(RecordingConnector):
    async def execute(self, capability: str, payload: dict[str, Any]) -> ConnectorOutcome:
        self.calls.append((capability, payload))
        raise ConnectorError("provider rejected request", retryable=False)


class UnexpectedConnector(RecordingConnector):
    async def execute(self, capability: str, payload: dict[str, Any]) -> ConnectorOutcome:
        self.calls.append((capability, payload))
        raise ValueError("malformed success response after dispatch")


class WpsResourceConnector(RecordingConnector):
    def resource_context(self, capability: str) -> dict[str, str]:
        return {"drive_id": "drive-1", "parent_id": "parent-1"}


def build_service(tmp_path, connector=None):
    store = SqliteActionStore(tmp_path / "actions.db")
    selected_connector = connector or RecordingConnector()
    service = ActionService(
        registry=build_mvp_capability_registry(),
        store=store,
        connectors={"feishu": selected_connector},
    )
    return service, store, selected_connector


def grant_feishu(store: SqliteActionStore, owner_id: str = "owner-a"):
    return store.grant(
        owner_id=owner_id,
        provider_id="feishu",
        capabilities=("document.create",),
        purpose="career_artifact_creation",
    )


def test_preview_requires_active_grant_and_normalizes_payload_hash(tmp_path) -> None:
    service, store, _ = build_service(tmp_path)
    try:
        with pytest.raises(GrantRequiredError):
            service.preview("owner-a", "feishu", "document.create", {"title": "Plan"})

        grant_feishu(store)
        first = service.preview(
            "owner-a",
            "feishu",
            "document.create",
            {"title": "Plan", "parent_token": "career"},
        )
        second = service.preview(
            "owner-a",
            "feishu",
            "document.create",
            {"parent_token": "career", "title": "Plan"},
        )

        assert first.preview_hash == second.preview_hash
        assert first.owner_id == "owner-a"
        assert first.payload == {"content": "", "parent_token": "career", "title": "Plan"}
    finally:
        store.close()


@pytest.mark.asyncio
async def test_apply_rejects_hash_drift_and_confirmation_replay(tmp_path) -> None:
    service, store, connector = build_service(tmp_path)
    try:
        grant_feishu(store)
        preview = service.preview(
            "owner-a", "feishu", "document.create", {"title": "Career plan"}
        )
        confirmation = service.confirm("owner-a", preview.id, preview.preview_hash)

        with pytest.raises(ConfirmationError, match="preview hash"):
            await service.apply(
                "owner-a",
                preview.id,
                confirmation.token,
                "different-hash",
                "request-drift",
            )

        receipt = await service.apply(
            "owner-a",
            preview.id,
            confirmation.token,
            preview.preview_hash,
            "request-1",
        )
        same_receipt = await service.apply(
            "owner-a",
            preview.id,
            confirmation.token,
            preview.preview_hash,
            "request-1",
        )

        assert receipt == same_receipt
        assert receipt.status == "completed"
        assert len(connector.calls) == 1
        with pytest.raises(ConfirmationError, match="already used"):
            await service.apply(
                "owner-a",
                preview.id,
                confirmation.token,
                preview.preview_hash,
                "request-2",
            )
        assert len(connector.calls) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_revocation_after_confirmation_blocks_execution(tmp_path) -> None:
    service, store, connector = build_service(tmp_path)
    try:
        grant = grant_feishu(store)
        preview = service.preview("owner-a", "feishu", "document.create", {"title": "Plan"})
        confirmation = service.confirm("owner-a", preview.id, preview.preview_hash)
        assert store.revoke("owner-a", grant.id) is True

        with pytest.raises(GrantRequiredError):
            await service.apply(
                "owner-a",
                preview.id,
                confirmation.token,
                preview.preview_hash,
                "request-1",
            )
        assert connector.calls == []
    finally:
        store.close()


@pytest.mark.asyncio
async def test_timeout_is_stored_as_unknown_without_automatic_retry(tmp_path) -> None:
    connector = TimingOutConnector()
    service, store, _ = build_service(tmp_path, connector)
    try:
        grant_feishu(store)
        preview = service.preview("owner-a", "feishu", "document.create", {"title": "Plan"})
        confirmation = service.confirm("owner-a", preview.id, preview.preview_hash)

        receipt = await service.apply(
            "owner-a",
            preview.id,
            confirmation.token,
            preview.preview_hash,
            "request-timeout",
        )

        assert receipt.status == "unknown"
        assert receipt.retryable is False
        assert len(connector.calls) == 1
        await asyncio.sleep(0)
        assert len(connector.calls) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_read_capability_does_not_require_per_call_confirmation(tmp_path) -> None:
    connector = RecordingConnector()
    store = SqliteActionStore(tmp_path / "actions.db")
    service = ActionService(
        registry=build_mvp_capability_registry(),
        store=store,
        connectors={"netease_mail": connector},
    )
    try:
        store.grant(
            owner_id="owner-a",
            provider_id="netease_mail",
            capabilities=("email.search_recruiting",),
            purpose="recruiting_email_assistance",
        )
        preview = service.preview(
            "owner-a", "netease_mail", "email.search_recruiting", {"limit": 10}
        )

        receipt = await service.apply(
            "owner-a",
            preview.id,
            None,
            preview.preview_hash,
            "read-request-1",
        )

        assert receipt.status == "completed"
        assert len(connector.calls) == 1
    finally:
        store.close()


def test_reconfirming_used_preview_requires_a_new_preview(tmp_path) -> None:
    service, store, _ = build_service(tmp_path)
    try:
        grant_feishu(store)
        preview = service.preview("owner-a", "feishu", "document.create", {"title": "Plan"})
        service.confirm("owner-a", preview.id, preview.preview_hash)

        with pytest.raises(ConfirmationError, match="already confirmed"):
            service.confirm("owner-a", preview.id, preview.preview_hash)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_idempotency_key_is_bound_across_previews(tmp_path) -> None:
    service, store, connector = build_service(tmp_path)
    try:
        grant_feishu(store)
        first = service.preview("owner-a", "feishu", "document.create", {"title": "First"})
        first_confirmation = service.confirm("owner-a", first.id, first.preview_hash)
        await service.apply(
            "owner-a", first.id, first_confirmation.token, first.preview_hash, "shared-key"
        )
        second = service.preview("owner-a", "feishu", "document.create", {"title": "Second"})
        second_confirmation = service.confirm("owner-a", second.id, second.preview_hash)

        with pytest.raises(IdempotencyConflictError):
            await service.apply(
                "owner-a", second.id, second_confirmation.token, second.preview_hash, "shared-key"
            )
        assert len(connector.calls) == 1
    finally:
        store.close()


def test_grant_resource_constraints_are_enforced_during_preview(tmp_path) -> None:
    service, store, _ = build_service(tmp_path)
    try:
        store.grant(
            owner_id="owner-a",
            provider_id="feishu",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
            resource_constraints={"parent_token": ["allowed-folder"]},
        )

        with pytest.raises(ResourceConstraintError):
            service.preview(
                "owner-a",
                "feishu",
                "document.create",
                {"title": "Plan", "parent_token": "other-folder"},
            )
        with pytest.raises(ResourceConstraintError):
            service.preview(
                "owner-a", "feishu", "document.create", {"title": "No target"}
            )
    finally:
        store.close()


def test_multi_capability_grant_only_applies_relevant_constraints(tmp_path) -> None:
    service, store, _ = build_service(tmp_path)
    try:
        store.grant(
            owner_id="owner-a",
            provider_id="feishu",
            capabilities=("document.create", "calendar.create"),
            purpose="career_actions",
            resource_constraints={
                "parent_token": ["allowed-folder"],
                "calendar_id": ["primary"],
            },
        )

        preview = service.preview(
            "owner-a",
            "feishu",
            "document.create",
            {"title": "Plan", "parent_token": "allowed-folder"},
        )

        assert preview.payload["parent_token"] == "allowed-folder"
    finally:
        store.close()


@pytest.mark.asyncio
async def test_provider_failure_creates_terminal_failed_receipt(tmp_path) -> None:
    connector = FailingConnector()
    service, store, _ = build_service(tmp_path, connector)
    try:
        grant_feishu(store)
        preview = service.preview("owner-a", "feishu", "document.create", {"title": "Plan"})
        confirmation = service.confirm("owner-a", preview.id, preview.preview_hash)

        receipt = await service.apply(
            "owner-a", preview.id, confirmation.token, preview.preview_hash, "failed-request"
        )
        repeated = await service.apply(
            "owner-a", preview.id, confirmation.token, preview.preview_hash, "failed-request"
        )

        assert receipt.status == "failed"
        assert receipt == repeated
        assert len(connector.calls) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_unexpected_post_dispatch_error_is_recorded_as_unknown(tmp_path) -> None:
    connector = UnexpectedConnector()
    service, store, _ = build_service(tmp_path, connector)
    try:
        grant_feishu(store)
        preview = service.preview("owner-a", "feishu", "document.create", {"title": "Plan"})
        confirmation = service.confirm("owner-a", preview.id, preview.preview_hash)

        receipt = await service.apply(
            "owner-a", preview.id, confirmation.token, preview.preview_hash, "unknown-request"
        )

        assert receipt.status == "unknown"
        assert receipt.retryable is False
    finally:
        store.close()


@pytest.mark.asyncio
async def test_idempotency_key_is_owner_wide_across_providers(tmp_path) -> None:
    connector = RecordingConnector()
    store = SqliteActionStore(tmp_path / "actions.db")
    service = ActionService(
        registry=build_mvp_capability_registry(),
        store=store,
        connectors={"feishu": connector, "wps": connector},
    )
    try:
        grant_feishu(store)
        store.grant(
            owner_id="owner-a",
            provider_id="wps",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
        )
        first = service.preview("owner-a", "feishu", "document.create", {"title": "First"})
        first_confirmation = service.confirm("owner-a", first.id, first.preview_hash)
        await service.apply(
            "owner-a", first.id, first_confirmation.token, first.preview_hash, "owner-key"
        )
        second = service.preview("owner-a", "wps", "document.create", {"name": "Second"})
        second_confirmation = service.confirm("owner-a", second.id, second.preview_hash)

        with pytest.raises(IdempotencyConflictError):
            await service.apply(
                "owner-a", second.id, second_confirmation.token, second.preview_hash, "owner-key"
            )
        assert len(connector.calls) == 1
    finally:
        store.close()


def test_wps_constraints_apply_to_connector_configured_resources(tmp_path) -> None:
    connector = WpsResourceConnector()
    store = SqliteActionStore(tmp_path / "actions.db")
    service = ActionService(
        registry=build_mvp_capability_registry(),
        store=store,
        connectors={"wps": connector},
    )
    try:
        store.grant(
            owner_id="owner-a",
            provider_id="wps",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
            resource_constraints={"drive_id": ["different-drive"]},
        )

        with pytest.raises(ResourceConstraintError):
            service.preview("owner-a", "wps", "document.create", {"name": "Plan"})
    finally:
        store.close()
