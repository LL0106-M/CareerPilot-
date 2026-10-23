"""SQLite persistence for owner-scoped grants."""

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from careerpilot.actions.models import AuthorizationState, PermissionGrant
from careerpilot.actions.registry import CapabilityRegistry


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SqliteActionStore:
    def __init__(self, path: str | Path) -> None:
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS permission_grants (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                capabilities_json TEXT NOT NULL,
                purpose TEXT NOT NULL,
                scope_snapshot_json TEXT NOT NULL,
                resource_constraints_json TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_permission_grants_owner_provider
            ON permission_grants (owner_id, provider_id, revoked_at)
            """
        )
        self._connection.commit()

    def grant(
        self,
        *,
        owner_id: str,
        provider_id: str,
        capabilities: Iterable[str],
        purpose: str,
        scope_snapshot: Iterable[str] = (),
        resource_constraints: dict[str, Any] | None = None,
    ) -> PermissionGrant:
        grant = PermissionGrant(
            id=str(uuid4()),
            owner_id=owner_id,
            provider_id=provider_id,
            capabilities=tuple(capabilities),
            purpose=purpose,
            scope_snapshot=tuple(scope_snapshot),
            resource_constraints=dict(resource_constraints or {}),
            granted_at=_utc_now(),
        )
        self._connection.execute(
            """
            INSERT INTO permission_grants (
                id, owner_id, provider_id, capabilities_json, purpose,
                scope_snapshot_json, resource_constraints_json, granted_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                grant.id,
                grant.owner_id,
                grant.provider_id,
                json.dumps(grant.capabilities),
                grant.purpose,
                json.dumps(grant.scope_snapshot),
                json.dumps(grant.resource_constraints),
                grant.granted_at,
                grant.revoked_at,
            ),
        )
        self._connection.commit()
        return grant

    def find_active_grant(
        self, owner_id: str, provider_id: str, capability: str
    ) -> PermissionGrant | None:
        rows = self._connection.execute(
            """
            SELECT * FROM permission_grants
            WHERE owner_id = ? AND provider_id = ? AND revoked_at IS NULL
            ORDER BY granted_at DESC
            """,
            (owner_id, provider_id),
        ).fetchall()
        for row in rows:
            grant = self._row_to_grant(row)
            if capability in grant.capabilities:
                return grant
        return None

    def list_authorization(
        self, owner_id: str, registry: CapabilityRegistry
    ) -> tuple[AuthorizationState, ...]:
        states: list[AuthorizationState] = []
        for capability_id in registry.capability_ids:
            provider_id, capability = capability_id.split(":", maxsplit=1)
            grant = self.find_active_grant(owner_id, provider_id, capability)
            states.append(
                AuthorizationState(
                    provider_id=provider_id,
                    capability=capability,
                    grant_state="granted" if grant else "not_granted",
                    grant_id=grant.id if grant else None,
                    scope_snapshot=grant.scope_snapshot if grant else (),
                )
            )
        return tuple(states)

    def revoke(self, owner_id: str, grant_id: str) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE permission_grants SET revoked_at = ?
            WHERE id = ? AND owner_id = ? AND revoked_at IS NULL
            """,
            (_utc_now(), grant_id, owner_id),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _row_to_grant(row: sqlite3.Row) -> PermissionGrant:
        return PermissionGrant(
            id=row["id"],
            owner_id=row["owner_id"],
            provider_id=row["provider_id"],
            capabilities=tuple(json.loads(row["capabilities_json"])),
            purpose=row["purpose"],
            scope_snapshot=tuple(json.loads(row["scope_snapshot_json"])),
            resource_constraints=json.loads(row["resource_constraints_json"]),
            granted_at=row["granted_at"],
            revoked_at=row["revoked_at"],
        )
