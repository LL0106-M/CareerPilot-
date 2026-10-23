"""SQLite persistence for owner-scoped grants."""

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from careerpilot.actions.models import (
    ActionConfirmation,
    ActionPreview,
    ActionReceipt,
    AuthorizationState,
    PermissionGrant,
)
from careerpilot.actions.registry import CapabilityRegistry


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SqliteActionStore:
    def __init__(self, path: str | Path) -> None:
        resolved_path = Path(path)
        if str(path) != ":memory:":
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
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
            CREATE TABLE IF NOT EXISTS action_executions (
                owner_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                action_id TEXT NOT NULL,
                preview_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_id TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, provider_id, idempotency_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS action_previews (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                preview_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS action_confirmations (
                action_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                preview_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                used_idempotency_key TEXT
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS action_receipts (
                id TEXT PRIMARY KEY,
                action_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                status TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                external_reference TEXT,
                observations_json TEXT NOT NULL,
                retryable INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(owner_id, action_id, idempotency_key)
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

    def revoke(self, owner_id: str, grant_id: str, provider_id: str | None = None) -> bool:
        provider_clause = " AND provider_id = ?" if provider_id is not None else ""
        parameters: tuple[str, ...] = (
            (_utc_now(), grant_id, owner_id, provider_id)
            if provider_id is not None
            else (_utc_now(), grant_id, owner_id)
        )
        cursor = self._connection.execute(
            f"""
            UPDATE permission_grants SET revoked_at = ?
            WHERE id = ? AND owner_id = ? AND revoked_at IS NULL{provider_clause}
            """,
            parameters,
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def save_preview(self, preview: ActionPreview) -> None:
        self._connection.execute(
            """
            INSERT INTO action_previews (
                id, owner_id, provider_id, capability, payload_json, preview_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                preview.id,
                preview.owner_id,
                preview.provider_id,
                preview.capability,
                json.dumps(preview.payload, sort_keys=True, separators=(",", ":")),
                preview.preview_hash,
                preview.created_at,
            ),
        )
        self._connection.commit()

    def get_preview(self, owner_id: str, action_id: str) -> ActionPreview | None:
        row = self._connection.execute(
            "SELECT * FROM action_previews WHERE id = ? AND owner_id = ?",
            (action_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        return ActionPreview(
            id=row["id"],
            owner_id=row["owner_id"],
            provider_id=row["provider_id"],
            capability=row["capability"],
            payload=json.loads(row["payload_json"]),
            preview_hash=row["preview_hash"],
            created_at=row["created_at"],
        )

    def save_confirmation(self, confirmation: ActionConfirmation) -> bool:
        try:
            self._connection.execute(
                """
            INSERT INTO action_confirmations (
                action_id, owner_id, token, preview_hash, created_at, used_idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    confirmation.action_id,
                    confirmation.owner_id,
                    confirmation.token,
                    confirmation.preview_hash,
                    confirmation.created_at,
                    confirmation.used_idempotency_key,
                ),
            )
        except sqlite3.IntegrityError:
            self._connection.rollback()
            return False
        self._connection.commit()
        return True

    def get_confirmation(self, owner_id: str, action_id: str) -> ActionConfirmation | None:
        row = self._connection.execute(
            "SELECT * FROM action_confirmations WHERE action_id = ? AND owner_id = ?",
            (action_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        return ActionConfirmation(
            action_id=row["action_id"],
            owner_id=row["owner_id"],
            token=row["token"],
            preview_hash=row["preview_hash"],
            created_at=row["created_at"],
            used_idempotency_key=row["used_idempotency_key"],
        )

    def consume_confirmation(self, owner_id: str, action_id: str, idempotency_key: str) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE action_confirmations SET used_idempotency_key = ?
            WHERE action_id = ? AND owner_id = ? AND used_idempotency_key IS NULL
            """,
            (idempotency_key, action_id, owner_id),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def reserve_execution(
        self,
        *,
        owner_id: str,
        provider_id: str,
        idempotency_key: str,
        action_id: str,
        preview_hash: str,
        requires_confirmation: bool,
    ) -> str:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                existing = self._connection.execute(
                    """
                    SELECT action_id, preview_hash FROM action_executions
                    WHERE owner_id = ? AND provider_id = ? AND idempotency_key = ?
                    """,
                    (owner_id, provider_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    self._connection.commit()
                    same_execution = (
                        existing["action_id"] == action_id
                        and existing["preview_hash"] == preview_hash
                    )
                    if same_execution:
                        return "existing"
                    return "conflict"
                self._connection.execute(
                    """
                    INSERT INTO action_executions (
                        owner_id, provider_id, idempotency_key, action_id,
                        preview_hash, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'applying', ?)
                    """,
                    (
                        owner_id,
                        provider_id,
                        idempotency_key,
                        action_id,
                        preview_hash,
                        _utc_now(),
                    ),
                )
                if requires_confirmation:
                    cursor = self._connection.execute(
                        """
                        UPDATE action_confirmations SET used_idempotency_key = ?
                        WHERE action_id = ? AND owner_id = ? AND used_idempotency_key IS NULL
                        """,
                        (idempotency_key, action_id, owner_id),
                    )
                    if cursor.rowcount != 1:
                        self._connection.rollback()
                        return "confirmation_used"
                self._connection.commit()
                return "reserved"
            except Exception:
                self._connection.rollback()
                raise

    def save_receipt(self, receipt: ActionReceipt) -> None:
        with self._connection:
            self._connection.execute(
                """
            INSERT INTO action_receipts (
                id, action_id, owner_id, provider_id, status, idempotency_key,
                external_reference, observations_json, retryable, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    receipt.id,
                    receipt.action_id,
                    receipt.owner_id,
                    receipt.provider_id,
                    receipt.status,
                    receipt.idempotency_key,
                    receipt.external_reference,
                    json.dumps(receipt.observations),
                    int(receipt.retryable),
                    receipt.created_at,
                ),
            )
            self._connection.execute(
                """
                UPDATE action_executions SET status = ?, receipt_id = ?
                WHERE owner_id = ? AND provider_id = ? AND idempotency_key = ?
                """,
                (
                    receipt.status,
                    receipt.id,
                    receipt.owner_id,
                    receipt.provider_id,
                    receipt.idempotency_key,
                ),
            )

    def find_receipt(
        self, owner_id: str, action_id: str, idempotency_key: str
    ) -> ActionReceipt | None:
        row = self._connection.execute(
            """
            SELECT * FROM action_receipts
            WHERE owner_id = ? AND action_id = ? AND idempotency_key = ?
            """,
            (owner_id, action_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return ActionReceipt(
            id=row["id"],
            action_id=row["action_id"],
            owner_id=row["owner_id"],
            provider_id=row["provider_id"],
            status=row["status"],
            idempotency_key=row["idempotency_key"],
            external_reference=row["external_reference"],
            observations=tuple(json.loads(row["observations_json"])),
            retryable=bool(row["retryable"]),
            created_at=row["created_at"],
        )

    def find_receipt_by_key(
        self, owner_id: str, provider_id: str, idempotency_key: str
    ) -> ActionReceipt | None:
        row = self._connection.execute(
            """
            SELECT * FROM action_receipts
            WHERE owner_id = ? AND provider_id = ? AND idempotency_key = ?
            """,
            (owner_id, provider_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return self.find_receipt(owner_id, row["action_id"], idempotency_key)

    def last_used_at(self, owner_id: str, provider_id: str) -> str | None:
        row = self._connection.execute(
            """
            SELECT MAX(created_at) AS last_used_at FROM action_receipts
            WHERE owner_id = ? AND provider_id = ?
            """,
            (owner_id, provider_id),
        ).fetchone()
        return row["last_used_at"] if row else None

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
