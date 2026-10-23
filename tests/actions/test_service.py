import asyncio
from typing import Any

import pytest

from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.service import (
    ActionService,
    ConfirmationError,
    ConnectorOutcome,
    GrantRequiredError,
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
            {"title": "Plan", "folder": "career"},
        )
        second = service.preview(
            "owner-a",
            "feishu",
            "document.create",
            {"folder": "career", "title": "Plan"},
        )

        assert first.preview_hash == second.preview_hash
        assert first.owner_id == "owner-a"
        assert first.payload == {"folder": "career", "title": "Plan"}
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
