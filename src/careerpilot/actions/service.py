"""Governed preview-confirm-apply action boundary."""

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from careerpilot.actions.models import (
    ActionConfirmation,
    ActionPreview,
    ActionReceipt,
)
from careerpilot.actions.registry import CapabilityRegistry
from careerpilot.actions.store import SqliteActionStore, _utc_now


class ActionError(RuntimeError):
    pass


class GrantRequiredError(ActionError):
    pass


class ConfirmationError(ActionError):
    pass


@dataclass(frozen=True, slots=True)
class ConnectorOutcome:
    external_reference: str | None = None
    observations: tuple[str, ...] = ()


class Connector(Protocol):
    async def probe(self) -> bool: ...

    async def execute(self, capability: str, payload: dict[str, Any]) -> ConnectorOutcome: ...

    async def verify(self, outcome: ConnectorOutcome) -> bool: ...


def _normalized_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    normalized = json.loads(serialized)
    return normalized, hashlib.sha256(serialized.encode()).hexdigest()


class ActionService:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        store: SqliteActionStore,
        connectors: dict[str, Connector],
    ) -> None:
        self._registry = registry
        self._store = store
        self._connectors = connectors

    def preview(
        self,
        owner_id: str,
        provider_id: str,
        capability: str,
        payload: dict[str, Any],
    ) -> ActionPreview:
        self._registry.get(provider_id, capability)
        self._require_grant(owner_id, provider_id, capability)
        normalized, preview_hash = _normalized_payload(payload)
        preview = ActionPreview(
            id=str(uuid4()),
            owner_id=owner_id,
            provider_id=provider_id,
            capability=capability,
            payload=normalized,
            preview_hash=preview_hash,
            created_at=_utc_now(),
        )
        self._store.save_preview(preview)
        return preview

    def confirm(
        self, owner_id: str, action_id: str, preview_hash: str
    ) -> ActionConfirmation:
        preview = self._store.get_preview(owner_id, action_id)
        if preview is None:
            raise ConfirmationError("action preview was not found")
        if preview.preview_hash != preview_hash:
            raise ConfirmationError("preview hash does not match")
        self._require_grant(owner_id, preview.provider_id, preview.capability)
        confirmation = ActionConfirmation(
            action_id=action_id,
            owner_id=owner_id,
            token=secrets.token_urlsafe(32),
            preview_hash=preview_hash,
            created_at=_utc_now(),
        )
        self._store.save_confirmation(confirmation)
        return confirmation

    async def apply(
        self,
        owner_id: str,
        action_id: str,
        confirmation_token: str | None,
        preview_hash: str,
        idempotency_key: str,
    ) -> ActionReceipt:
        existing = self._store.find_receipt(owner_id, action_id, idempotency_key)
        if existing is not None:
            return existing

        preview = self._store.get_preview(owner_id, action_id)
        if preview is None:
            raise ConfirmationError("action preview was not found")
        definition = self._registry.get(preview.provider_id, preview.capability)
        if preview.preview_hash != preview_hash:
            raise ConfirmationError("preview hash does not match")
        self._require_grant(owner_id, preview.provider_id, preview.capability)
        if definition.requires_confirmation:
            confirmation = self._store.get_confirmation(owner_id, action_id)
            if confirmation is None or confirmation.token != confirmation_token:
                raise ConfirmationError("confirmation is invalid")
            if confirmation.preview_hash != preview_hash:
                raise ConfirmationError("preview hash does not match")
            if confirmation.used_idempotency_key is not None:
                raise ConfirmationError("confirmation was already used")
            if not self._store.consume_confirmation(owner_id, action_id, idempotency_key):
                raise ConfirmationError("confirmation was already used")

        connector = self._connectors[preview.provider_id]
        try:
            outcome = await connector.execute(preview.capability, preview.payload)
            verified = await connector.verify(outcome)
            status = "completed" if verified else "unknown"
            observations = outcome.observations
            external_reference = outcome.external_reference
        except TimeoutError:
            status = "unknown"
            observations = ("provider outcome is uncertain",)
            external_reference = None

        receipt = ActionReceipt(
            id=str(uuid4()),
            action_id=action_id,
            owner_id=owner_id,
            provider_id=preview.provider_id,
            status=status,
            idempotency_key=idempotency_key,
            external_reference=external_reference,
            observations=observations,
            retryable=False,
            created_at=_utc_now(),
        )
        self._store.save_receipt(receipt)
        return receipt

    def _require_grant(self, owner_id: str, provider_id: str, capability: str) -> None:
        grant = self._store.find_active_grant(owner_id, provider_id, capability)
        if grant is None:
            raise GrantRequiredError(f"active grant required for {provider_id}:{capability}")
