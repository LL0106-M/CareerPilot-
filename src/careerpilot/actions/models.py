"""Domain models for provider capabilities and user authorization."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    provider_id: str
    capability: str
    risk_level: str
    write: bool
    requires_confirmation: bool
    required_scopes: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return f"{self.provider_id}:{self.capability}"


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    provider_id: str
    display_name: str
    auth_mode: str
    capabilities: tuple[CapabilityDefinition, ...]


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    id: str
    owner_id: str
    provider_id: str
    capabilities: tuple[str, ...]
    purpose: str
    scope_snapshot: tuple[str, ...]
    resource_constraints: dict[str, Any] = field(default_factory=dict)
    granted_at: str = ""
    revoked_at: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationState:
    provider_id: str
    capability: str
    grant_state: str
    grant_id: str | None = None
    scope_snapshot: tuple[str, ...] = ()
    last_used_at: str | None = None


@dataclass(frozen=True, slots=True)
class ActionPreview:
    id: str
    owner_id: str
    provider_id: str
    capability: str
    payload: dict[str, Any]
    preview_hash: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ActionConfirmation:
    action_id: str
    owner_id: str
    token: str
    preview_hash: str
    created_at: str
    used_idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class ActionReceipt:
    id: str
    action_id: str
    owner_id: str
    provider_id: str
    status: str
    idempotency_key: str
    external_reference: str | None
    observations: tuple[str, ...]
    retryable: bool
    created_at: str
