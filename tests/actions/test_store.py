import sqlite3

from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.store import SqliteActionStore


def test_grants_are_owner_scoped_and_visible_by_capability(tmp_path) -> None:
    store = SqliteActionStore(tmp_path / "actions.db")
    registry = build_mvp_capability_registry()
    try:
        grant = store.grant(
            owner_id="owner-a",
            provider_id="feishu",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
            scope_snapshot=("docs:write",),
        )

        assert store.find_active_grant("owner-a", "feishu", "document.create") == grant
        assert store.find_active_grant("owner-b", "feishu", "document.create") is None
        states = store.list_authorization("owner-a", registry)
        feishu_document = next(
            item
            for item in states
            if item.provider_id == "feishu" and item.capability == "document.create"
        )
        assert feishu_document.grant_state == "granted"
        assert feishu_document.grant_id == grant.id
        assert feishu_document.scope_snapshot == ("docs:write",)
    finally:
        store.close()


def test_revoked_grant_is_immediately_unusable(tmp_path) -> None:
    store = SqliteActionStore(tmp_path / "actions.db")
    try:
        grant = store.grant(
            owner_id="owner-a",
            provider_id="wps",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
        )

        assert store.revoke("owner-b", grant.id) is False
        assert store.revoke("owner-a", grant.id) is True
        assert store.find_active_grant("owner-a", "wps", "document.create") is None
    finally:
        store.close()


def test_store_creates_default_parent_directory(tmp_path) -> None:
    path = tmp_path / "nested" / "actions" / "careerpilot.db"

    store = SqliteActionStore(path)
    try:
        assert path.exists()
    finally:
        store.close()


def test_store_migrates_provider_scoped_idempotency_keys(tmp_path) -> None:
    path = tmp_path / "actions.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE action_executions (
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
    connection.execute(
        """
        CREATE TABLE action_receipts (
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
    receipts = (
        (
            "receipt-wps",
            "a-action-wps",
            "owner-a",
            "wps",
            "completed",
            "shared-key",
            "wps-file",
            "[]",
            0,
            "2026-10-23T11:00:00+00:00",
        ),
        (
            "receipt-feishu",
            "z-action-feishu",
            "owner-a",
            "feishu",
            "completed",
            "shared-key",
            "feishu-doc",
            "[]",
            0,
            "2026-10-23T10:00:00+00:00",
        ),
    )
    connection.executemany(
        "INSERT INTO action_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", receipts
    )
    executions = (
        (
            "owner-a",
            "feishu",
            "shared-key",
            "z-action-feishu",
            "hash-feishu",
            "completed",
            "receipt-feishu",
            "2026-10-23T10:00:00+00:00",
        ),
        (
            "owner-a",
            "wps",
            "shared-key",
            "a-action-wps",
            "hash-wps",
            "completed",
            "receipt-wps",
            "2026-10-23T11:00:00+00:00",
        ),
    )
    connection.executemany(
        "INSERT INTO action_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", executions
    )
    connection.commit()
    connection.close()

    store = SqliteActionStore(path)
    try:
        columns = store._connection.execute("PRAGMA table_info(action_executions)").fetchall()
        primary_key = [
            row["name"]
            for row in sorted(columns, key=lambda row: row["pk"])
            if row["pk"]
        ]

        assert primary_key == ["owner_id", "idempotency_key"]
        receipt = store.find_receipt_by_key("owner-a", "wps", "shared-key")
        assert receipt is not None
        assert receipt.id == "receipt-feishu"
        assert receipt.action_id == "z-action-feishu"
    finally:
        store.close()
