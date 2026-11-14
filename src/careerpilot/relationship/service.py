from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from careerpilot.relationship.models import BOBO_CORE, RELATIONSHIP_VALUES


class RelationshipService:
    """Reversible interaction-style projection; never a career evidence source."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS relationship_profiles (
                owner_id TEXT NOT NULL, dimension TEXT NOT NULL, value TEXT NOT NULL,
                source TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL,
                signal_count INTEGER NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, dimension)
            );
            CREATE INDEX IF NOT EXISTS relationship_profile_owner_idx
                ON relationship_profiles(owner_id, status, updated_at DESC);
            """
        )
        self._connection.commit()

    def record_signal(
        self,
        owner_id: str,
        *,
        dimension: str,
        value: str,
        source: str,
        explicit: bool,
    ) -> dict[str, object]:
        allowed_values = RELATIONSHIP_VALUES.get(dimension)
        if allowed_values is None:
            raise ValueError(f"unsupported relationship dimension: {dimension}")
        if value not in allowed_values:
            raise ValueError(f"unsupported value for {dimension}: {value}")
        existing = self._connection.execute(
            """SELECT * FROM relationship_profiles
            WHERE owner_id = ? AND dimension = ?""",
            (owner_id, dimension),
        ).fetchone()
        if (
            existing is not None
            and existing["status"] == "confirmed"
            and existing["value"] != value
            and not explicit
        ):
            return self._decode(existing)
        same_value = existing is not None and existing["value"] == value
        signal_count = int(existing["signal_count"]) + 1 if same_value else 1
        status = "confirmed" if explicit or signal_count >= 3 else "candidate"
        confidence = 1.0 if explicit else min(0.9, 0.3 + signal_count * 0.2)
        now = datetime.now(UTC).isoformat()
        created_at = str(existing["created_at"]) if existing is not None else now
        with self._connection:
            self._connection.execute(
                """INSERT INTO relationship_profiles
                (owner_id,dimension,value,source,confidence,status,signal_count,
                 created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(owner_id,dimension) DO UPDATE SET
                    value=excluded.value, source=excluded.source,
                    confidence=excluded.confidence, status=excluded.status,
                    signal_count=excluded.signal_count, updated_at=excluded.updated_at""",
                (
                    owner_id,
                    dimension,
                    value,
                    source,
                    confidence,
                    status,
                    signal_count,
                    created_at,
                    now,
                ),
            )
        row = self._connection.execute(
            """SELECT * FROM relationship_profiles
            WHERE owner_id = ? AND dimension = ?""",
            (owner_id, dimension),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def profile(self, owner_id: str) -> dict[str, object]:
        rows = self._connection.execute(
            """SELECT * FROM relationship_profiles WHERE owner_id = ?
            ORDER BY dimension""",
            (owner_id,),
        ).fetchall()
        return {
            "core": {
                "version": BOBO_CORE["version"],
                "principles": list(BOBO_CORE["principles"]),
            },
            "dimensions": [self._decode(row) for row in rows],
        }

    def reset(self, owner_id: str) -> None:
        self._connection.execute(
            "DELETE FROM relationship_profiles WHERE owner_id = ?", (owner_id,)
        )
        self._connection.commit()

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, object]:
        return {key: row[key] for key in row.keys() if key != "owner_id"}
