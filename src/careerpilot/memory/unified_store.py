from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from careerpilot.memory.models import (
    MemoryConfidence,
    MemoryEvidence,
    MemoryOrigin,
    MemoryRecord,
    MemoryRevision,
    MemorySensitivity,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
    MemoryUsage,
    MemoryUsageType,
)


class MemoryNotFoundError(LookupError):
    pass


class MemoryVersionConflictError(RuntimeError):
    pass


_TRANSITIONS = {
    MemoryStatus.CANDIDATE: {MemoryStatus.ACTIVE, MemoryStatus.DELETED},
    MemoryStatus.ACTIVE: {
        MemoryStatus.PAUSED,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.DELETED,
    },
    MemoryStatus.PAUSED: {
        MemoryStatus.ACTIVE,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.DELETED,
    },
    MemoryStatus.SUPERSEDED: set(),
    MemoryStatus.DELETED: set(),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SqliteUnifiedMemoryStore:
    """Owner-scoped authoritative memory state with revisions and audit."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS memory_records (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                normalized_content TEXT NOT NULL,
                status TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                origin TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_reference TEXT,
                confidence TEXT NOT NULL,
                importance INTEGER NOT NULL CHECK (importance BETWEEN 1 AND 5),
                version INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,
                expires_at TEXT,
                deleted_at TEXT,
                UNIQUE(owner_id, id)
            );
            CREATE INDEX IF NOT EXISTS memory_owner_state_idx
                ON memory_records(owner_id, status, type, updated_at DESC);
            CREATE INDEX IF NOT EXISTS memory_owner_normalized_idx
                ON memory_records(owner_id, type, normalized_content);

            CREATE TABLE IF NOT EXISTS memory_evidence (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                source_reference TEXT,
                excerpt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_id, memory_id)
                    REFERENCES memory_records(owner_id, id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS evidence_owner_memory_idx
                ON memory_evidence(owner_id, memory_id, created_at);

            CREATE TABLE IF NOT EXISTS memory_revisions (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                from_version INTEGER NOT NULL,
                to_version INTEGER NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_id, memory_id)
                    REFERENCES memory_records(owner_id, id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memory_usage (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                turn_id TEXT NOT NULL,
                usage_type TEXT NOT NULL,
                result_reference TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_id, memory_id)
                    REFERENCES memory_records(owner_id, id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memory_audit_events (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                actor_kind TEXT NOT NULL,
                version INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def create_memory(
        self,
        *,
        owner_id: str,
        memory_type: MemoryType,
        content: str,
        status: MemoryStatus,
        sensitivity: MemorySensitivity,
        origin: MemoryOrigin,
        source_type: MemorySourceType,
        confidence: MemoryConfidence,
        source_reference: str | None = None,
        importance: int = 3,
        expires_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        actor_kind: str = "system",
        memory_id: str | None = None,
    ) -> MemoryRecord:
        clean = " ".join(content.split())
        if not clean:
            raise ValueError("Memory content cannot be empty")
        if not 1 <= importance <= 5:
            raise ValueError("Memory importance must be between 1 and 5")
        created = _now()
        record_id = memory_id or str(uuid4())
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO memory_records (
                    id, owner_id, type, content, normalized_content, status, sensitivity,
                    origin, source_type, source_reference, confidence, importance, version,
                    metadata_json, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    owner_id,
                    memory_type.value,
                    clean,
                    clean.casefold(),
                    status.value,
                    sensitivity.value,
                    origin.value,
                    source_type.value,
                    source_reference,
                    confidence.value,
                    importance,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    _iso(created),
                    _iso(created),
                    _iso(expires_at),
                ),
            )
            self._audit(owner_id, record_id, "create", actor_kind, 1)
        return self.get_memory(owner_id, record_id, include_deleted=True)

    def get_memory(
        self, owner_id: str, memory_id: str, *, include_deleted: bool = False
    ) -> MemoryRecord:
        sql = "SELECT * FROM memory_records WHERE owner_id = ? AND id = ?"
        params: list[object] = [owner_id, memory_id]
        if not include_deleted:
            sql += " AND status != ?"
            params.append(MemoryStatus.DELETED.value)
        row = self._connection.execute(sql, params).fetchone()
        if row is None:
            raise MemoryNotFoundError("Memory not found")
        return self._record(row)

    def list_memories(
        self,
        owner_id: str,
        *,
        statuses: tuple[MemoryStatus, ...] | None = None,
        types: tuple[MemoryType, ...] | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> tuple[MemoryRecord, ...]:
        clauses = ["owner_id = ?"]
        params: list[object] = [owner_id]
        if statuses:
            clauses.append(f"status IN ({','.join('?' for _ in statuses)})")
            params.extend(item.value for item in statuses)
        else:
            clauses.append("status != ?")
            params.append(MemoryStatus.DELETED.value)
        if types:
            clauses.append(f"type IN ({','.join('?' for _ in types)})")
            params.extend(item.value for item in types)
        if query and query.strip():
            clauses.append("normalized_content LIKE ?")
            params.append(f"%{' '.join(query.split()).casefold()}%")
        params.append(max(1, min(limit, 200)))
        rows = self._connection.execute(
            f"""SELECT * FROM memory_records WHERE {' AND '.join(clauses)}
            ORDER BY importance DESC, updated_at DESC, rowid DESC LIMIT ?""",
            params,
        ).fetchall()
        return tuple(self._record(row) for row in rows)

    def list_active_memories(self, owner_id: str, *, limit: int = 100) -> tuple[MemoryRecord, ...]:
        now = _iso(_now())
        rows = self._connection.execute(
            """
            SELECT * FROM memory_records
            WHERE owner_id = ? AND status = 'active'
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY importance DESC, updated_at DESC, rowid DESC LIMIT ?
            """,
            (owner_id, now, max(1, min(limit, 200))),
        ).fetchall()
        return tuple(self._record(row) for row in rows)

    def update_memory(
        self,
        owner_id: str,
        memory_id: str,
        *,
        expected_version: int,
        actor_kind: str = "user",
        **changes: object,
    ) -> MemoryRecord:
        allowed = {"content", "type", "sensitivity", "confidence", "importance", "expires_at", "metadata"}
        if not changes or not set(changes) <= allowed:
            raise ValueError("Unsupported or empty memory update")
        current = self.get_memory(owner_id, memory_id, include_deleted=True)
        if current.version != expected_version:
            raise MemoryVersionConflictError("Memory version conflict")
        data = self._snapshot(current)
        data.update(changes)
        if "content" in changes:
            clean = " ".join(str(changes["content"]).split())
            if not clean:
                raise ValueError("Memory content cannot be empty")
            data["content"] = clean
        importance = int(data["importance"])
        if not 1 <= importance <= 5:
            raise ValueError("Memory importance must be between 1 and 5")
        after_version = expected_version + 1
        updated = _now()
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE memory_records SET content=?, normalized_content=?, type=?, sensitivity=?,
                    confidence=?, importance=?, expires_at=?, metadata_json=?, version=?, updated_at=?
                WHERE owner_id=? AND id=? AND version=?
                """,
                (
                    data["content"],
                    str(data["content"]).casefold(),
                    self._enum_value(data["type"]),
                    self._enum_value(data["sensitivity"]),
                    self._enum_value(data["confidence"]),
                    importance,
                    _iso(data["expires_at"]),
                    json.dumps(data["metadata"], ensure_ascii=False),
                    after_version,
                    _iso(updated),
                    owner_id,
                    memory_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise MemoryVersionConflictError("Memory version conflict")
            after = dict(data)
            after["version"] = after_version
            after["updated_at"] = updated
            self._revision(owner_id, memory_id, expected_version, after_version, self._snapshot(current), after)
            self._audit(owner_id, memory_id, "update", actor_kind, after_version)
        return self.get_memory(owner_id, memory_id, include_deleted=True)

    def transition_memory(
        self,
        owner_id: str,
        memory_id: str,
        *,
        expected_version: int,
        target: MemoryStatus,
        actor_kind: str = "user",
    ) -> MemoryRecord:
        current = self.get_memory(owner_id, memory_id, include_deleted=True)
        if current.version != expected_version:
            raise MemoryVersionConflictError("Memory version conflict")
        if target not in _TRANSITIONS[current.status]:
            raise ValueError(f"Invalid memory transition: {current.status.value} -> {target.value}")
        version = expected_version + 1
        now = _now()
        before = self._snapshot(current)
        after = dict(before)
        after.update(status=target, version=version, updated_at=now)
        if target is MemoryStatus.DELETED:
            after["deleted_at"] = now
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE memory_records
                SET status=?, version=?, updated_at=?, deleted_at=?
                WHERE owner_id=? AND id=? AND version=?""",
                (
                    target.value,
                    version,
                    _iso(now),
                    _iso(after.get("deleted_at")),
                    owner_id,
                    memory_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise MemoryVersionConflictError("Memory version conflict")
            self._revision(owner_id, memory_id, expected_version, version, before, after)
            self._audit(owner_id, memory_id, f"transition:{target.value}", actor_kind, version)
        return self.get_memory(owner_id, memory_id, include_deleted=True)

    def add_evidence(
        self,
        owner_id: str,
        memory_id: str,
        *,
        kind: str,
        excerpt: str,
        source_reference: str | None = None,
    ) -> MemoryEvidence:
        self.get_memory(owner_id, memory_id, include_deleted=True)
        evidence_id = str(uuid4())
        created = _now()
        bounded = excerpt.strip()[:1000]
        with self._connection:
            self._connection.execute(
                """INSERT INTO memory_evidence
                (id, memory_id, owner_id, kind, source_reference, excerpt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (evidence_id, memory_id, owner_id, kind, source_reference, bounded, _iso(created)),
            )
        return MemoryEvidence(
            evidence_id, memory_id, owner_id, kind, source_reference, bounded, created
        )

    def list_evidence(self, owner_id: str, memory_id: str) -> tuple[MemoryEvidence, ...]:
        self.get_memory(owner_id, memory_id, include_deleted=True)
        rows = self._connection.execute(
            "SELECT * FROM memory_evidence WHERE owner_id=? AND memory_id=? ORDER BY created_at, rowid",
            (owner_id, memory_id),
        ).fetchall()
        return tuple(
            MemoryEvidence(
                row["id"],
                row["memory_id"],
                row["owner_id"],
                row["kind"],
                row["source_reference"],
                row["excerpt"],
                _datetime(row["created_at"]),
            )
            for row in rows
        )

    def record_usage(
        self,
        owner_id: str,
        memory_id: str,
        *,
        turn_id: str,
        usage_type: MemoryUsageType,
        result_reference: str | None = None,
    ) -> MemoryUsage:
        current = self.get_memory(owner_id, memory_id)
        usage_id = str(uuid4())
        created = _now()
        with self._connection:
            self._connection.execute(
                """INSERT INTO memory_usage
                (id, memory_id, owner_id, turn_id, usage_type, result_reference, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    usage_id,
                    memory_id,
                    owner_id,
                    turn_id,
                    usage_type.value,
                    result_reference,
                    _iso(created),
                ),
            )
            self._connection.execute(
                "UPDATE memory_records SET last_used_at=? WHERE owner_id=? AND id=?",
                (_iso(created), owner_id, memory_id),
            )
            self._audit(owner_id, memory_id, "usage", "agent", current.version)
        return MemoryUsage(
            usage_id,
            memory_id,
            owner_id,
            turn_id,
            usage_type,
            result_reference,
            created,
        )

    def list_revisions(self, owner_id: str, memory_id: str) -> tuple[MemoryRevision, ...]:
        self.get_memory(owner_id, memory_id, include_deleted=True)
        rows = self._connection.execute(
            "SELECT * FROM memory_revisions WHERE owner_id=? AND memory_id=? ORDER BY to_version",
            (owner_id, memory_id),
        ).fetchall()
        return tuple(
            MemoryRevision(
                row["id"],
                row["memory_id"],
                row["owner_id"],
                row["from_version"],
                row["to_version"],
                json.loads(row["before_json"]),
                json.loads(row["after_json"]),
                _datetime(row["created_at"]),
            )
            for row in rows
        )

    def close(self) -> None:
        self._connection.close()

    def _revision(
        self,
        owner_id: str,
        memory_id: str,
        from_version: int,
        to_version: int,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        self._connection.execute(
            "INSERT INTO memory_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                memory_id,
                owner_id,
                from_version,
                to_version,
                json.dumps(before, ensure_ascii=False, default=self._json_default),
                json.dumps(after, ensure_ascii=False, default=self._json_default),
                _iso(_now()),
            ),
        )

    def _audit(
        self,
        owner_id: str,
        memory_id: str,
        operation: str,
        actor_kind: str,
        version: int,
    ) -> None:
        self._connection.execute(
            "INSERT INTO memory_audit_events VALUES (?, ?, ?, ?, ?, ?, '{}', ?)",
            (str(uuid4()), owner_id, memory_id, operation, actor_kind, version, _iso(_now())),
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            owner_id=row["owner_id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            status=MemoryStatus(row["status"]),
            sensitivity=MemorySensitivity(row["sensitivity"]),
            origin=MemoryOrigin(row["origin"]),
            source_type=MemorySourceType(row["source_type"]),
            source_reference=row["source_reference"],
            confidence=MemoryConfidence(row["confidence"]),
            importance=row["importance"],
            version=row["version"],
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
            last_used_at=_datetime(row["last_used_at"]),
            expires_at=_datetime(row["expires_at"]),
            deleted_at=_datetime(row["deleted_at"]),
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _snapshot(record: MemoryRecord) -> dict[str, Any]:
        return {
            "type": record.type,
            "content": record.content,
            "status": record.status,
            "sensitivity": record.sensitivity,
            "origin": record.origin,
            "source_type": record.source_type,
            "source_reference": record.source_reference,
            "confidence": record.confidence,
            "importance": record.importance,
            "version": record.version,
            "metadata": record.metadata,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "last_used_at": record.last_used_at,
            "expires_at": record.expires_at,
            "deleted_at": record.deleted_at,
        }

    @staticmethod
    def _enum_value(value: object) -> object:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _json_default(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "value"):
            return value.value
        raise TypeError(f"Cannot serialize {type(value)!r}")
