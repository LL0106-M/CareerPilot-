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
from careerpilot.actions.payloads import validate_capability_payload
from careerpilot.actions.registry import CapabilityRegistry
from careerpilot.actions.store import SqliteActionStore, _utc_now


class ActionError(RuntimeError):
    pass


class GrantRequiredError(ActionError):
    pass


class ConfirmationError(ActionError):
    pass


class IdempotencyConflictError(ActionError):
    pass


class ResourceConstraintError(ActionError):
    pass


class PayloadValidationError(ActionError):
    pass


class ConnectorError(ActionError):
    def __init__(self, message: str, *, retryable: bool, uncertain: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.uncertain = uncertain


@dataclass(frozen=True, slots=True)
class ConnectorOutcome:
    external_reference: str | None = None
    observations: tuple[str, ...] = ()
    verification_kind: str | None = None


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
        grant = self._require_grant(owner_id, provider_id, capability)
        try:
            validated = validate_capability_payload(provider_id, capability, payload)
        except (KeyError, ValueError) as error:
            raise PayloadValidationError("invalid capability payload") from error
        self._enforce_constraints(grant.resource_constraints, validated)
        normalized, preview_hash = _normalized_payload(validated)
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
        if not self._store.save_confirmation(confirmation):
            raise ConfirmationError("action preview was already confirmed; create a new preview")
        return confirmation

    async def apply(
        self,
        owner_id: str,
        action_id: str,
        confirmation_token: str | None,
        preview_hash: str,
        idempotency_key: str,
    ) -> ActionReceipt:
        preview = self._store.get_preview(owner_id, action_id)
        if preview is None:
            raise ConfirmationError("action preview was not found")
        definition = self._registry.get(preview.provider_id, preview.capability)
        if preview.preview_hash != preview_hash:
            raise ConfirmationError("preview hash does not match")
        grant = self._require_grant(owner_id, preview.provider_id, preview.capability)
        self._enforce_constraints(grant.resource_constraints, preview.payload)
        connector = self._connectors[preview.provider_id]
        if definition.requires_confirmation:
            confirmation = self._store.get_confirmation(owner_id, action_id)
            if confirmation is None or confirmation.token != confirmation_token:
                raise ConfirmationError("confirmation is invalid")
            if confirmation.preview_hash != preview_hash:
                raise ConfirmationError("preview hash does not match")
        reservation = self._store.reserve_execution(
            owner_id=owner_id,
            provider_id=preview.provider_id,
            idempotency_key=idempotency_key,
            action_id=action_id,
            preview_hash=preview_hash,
            requires_confirmation=definition.requires_confirmation,
        )
        if reservation == "conflict":
            raise IdempotencyConflictError("idempotency key is bound to a different preview")
        if reservation == "confirmation_used":
            raise ConfirmationError("confirmation was already used")
        if reservation == "existing":
            existing = self._store.find_receipt_by_key(
                owner_id, preview.provider_id, idempotency_key
            )
            if existing is not None:
                return existing
            raise ConfirmationError("action is already applying")

        try:
            outcome = await connector.execute(preview.capability, preview.payload)
            observations = outcome.observations
            external_reference = outcome.external_reference
            try:
                verified = await connector.verify(outcome)
            except Exception:
                verified = False
            status = "completed" if verified else "unknown"
            retryable = False
        except ConnectorError as error:
            status = "unknown" if error.uncertain else "failed"
            observations = ("provider outcome is uncertain",) if error.uncertain else (
                "provider rejected the request",
            )
            external_reference = None
            retryable = error.retryable
        except TimeoutError:
            status = "unknown"
            observations = ("provider outcome is uncertain",)
            external_reference = None
            retryable = False
        except Exception:
            status = "failed"
            observations = ("provider request failed",)
            external_reference = None
            retryable = False

        receipt = ActionReceipt(
            id=str(uuid4()),
            action_id=action_id,
            owner_id=owner_id,
            provider_id=preview.provider_id,
            status=status,
            idempotency_key=idempotency_key,
            external_reference=external_reference,
            observations=observations,
            retryable=retryable,
            created_at=_utc_now(),
        )
        self._store.save_receipt(receipt)
        return receipt

    async def connection_state(self, provider_id: str) -> tuple[bool, str]:
        connector = self._connectors.get(provider_id)
        if connector is None:
            return False, "not_configured"
        try:
            return True, "connected" if await connector.probe() else "unavailable"
        except Exception:
            return True, "unavailable"

    def _require_grant(self, owner_id: str, provider_id: str, capability: str):
        grant = self._store.find_active_grant(owner_id, provider_id, capability)
        if grant is None:
            raise GrantRequiredError(f"active grant required for {provider_id}:{capability}")
        return grant

    @staticmethod
    def _enforce_constraints(constraints: dict[str, Any], payload: dict[str, Any]) -> None:
        for field, allowed_values in constraints.items():
            if field in payload and payload[field] not in allowed_values:
                raise ResourceConstraintError(f"resource is outside grant constraint: {field}")
