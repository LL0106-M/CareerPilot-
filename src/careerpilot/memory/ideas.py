from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import uuid4

from careerpilot.memory.models import (
    MemoryOrigin,
    MemorySensitivity,
    MemorySourceType,
    MemoryType,
)
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import MemoryNotFoundError, MemoryVersionConflictError


class IdeaStage(StrEnum):
    CAPTURED = "captured"
    INCUBATING = "incubating"
    ACTIONABLE = "actionable"
    ACTED = "acted"
    VALIDATED = "validated"
    ARCHIVED = "archived"


class StorageAuthorization(StrEnum):
    GRANTED = "granted"
    CANDIDATE_ONLY = "candidate_only"
    DENIED = "denied"


class IdeaStorageDeniedError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class IdeaItem:
    id: str
    owner_id: str
    memory_id: str
    title: str
    stage: IdeaStage
    authorization: StorageAuthorization
    related_goal_memory_id: str | None
    next_step: str | None
    action_reference: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    last_reviewed_at: datetime | None


_STAGE_TRANSITIONS = {
    IdeaStage.CAPTURED: {IdeaStage.INCUBATING, IdeaStage.ACTIONABLE, IdeaStage.ARCHIVED},
    IdeaStage.INCUBATING: {IdeaStage.ACTIONABLE, IdeaStage.ARCHIVED},
    IdeaStage.ACTIONABLE: {IdeaStage.ACTED, IdeaStage.ARCHIVED},
    IdeaStage.ACTED: {IdeaStage.VALIDATED, IdeaStage.INCUBATING, IdeaStage.ARCHIVED},
    IdeaStage.VALIDATED: {IdeaStage.ARCHIVED},
    IdeaStage.ARCHIVED: set(),
}


def _now() -> datetime:
    return datetime.now(UTC)


class IdeaService:
    def __init__(self, memories: MemoryService) -> None:
        self.memories = memories
        self._connection = memories.store.connection
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS idea_items (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                title TEXT NOT NULL,
                stage TEXT NOT NULL,
                authorization TEXT NOT NULL,
                related_goal_memory_id TEXT,
                next_step TEXT,
                action_reference TEXT,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_reviewed_at TEXT,
                UNIQUE(owner_id, memory_id),
                FOREIGN KEY(owner_id, memory_id)
                    REFERENCES memory_records(owner_id, id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idea_owner_stage_idx
                ON idea_items(owner_id, stage, updated_at DESC);
            CREATE TABLE IF NOT EXISTS idea_audit_events (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                idea_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def capture_explicit(
        self,
        *,
        owner_id: str,
        raw_text: str,
        title: str,
        authorization: StorageAuthorization,
        source_reference: str | None = None,
        sensitivity: MemorySensitivity = MemorySensitivity.NORMAL,
        related_goal_memory_id: str | None = None,
    ) -> IdeaItem:
        if authorization is StorageAuthorization.DENIED:
            raise IdeaStorageDeniedError("Idea storage is not authorized")
        memory = self.memories.create_explicit(
            owner_id=owner_id,
            memory_type=MemoryType.IDEA,
            content=raw_text,
            sensitivity=sensitivity,
            source_type=MemorySourceType.CONVERSATION,
            source_reference=source_reference,
        )
        return self._create_or_existing(
            owner_id=owner_id,
            memory_id=memory.id,
            title=title,
            authorization=authorization,
            related_goal_memory_id=related_goal_memory_id,
        )

    def propose(
        self,
        *,
        owner_id: str,
        raw_text: str,
        title: str,
        authorization: StorageAuthorization,
        source_reference: str | None = None,
        sensitivity: MemorySensitivity = MemorySensitivity.NORMAL,
        related_goal_memory_id: str | None = None,
    ) -> IdeaItem:
        if authorization is StorageAuthorization.DENIED:
            raise IdeaStorageDeniedError("Candidate idea capture is not authorized")
        memory = self.memories.propose(
            owner_id=owner_id,
            memory_type=MemoryType.IDEA,
            content=raw_text,
            origin=MemoryOrigin.AGENT_EXTRACTED,
            source_type=MemorySourceType.CONVERSATION,
            source_reference=source_reference,
            sensitivity=sensitivity,
        )
        return self._create_or_existing(
            owner_id=owner_id,
            memory_id=memory.id,
            title=title,
            authorization=authorization,
            related_goal_memory_id=related_goal_memory_id,
        )

    def get(self, owner_id: str, idea_id: str) -> IdeaItem:
        row = self._connection.execute(
            "SELECT * FROM idea_items WHERE owner_id=? AND id=?", (owner_id, idea_id)
        ).fetchone()
        if row is None:
            raise MemoryNotFoundError("Idea not found")
        return self._item(row)

    def list(
        self,
        owner_id: str,
        *,
        stages: tuple[IdeaStage, ...] | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> tuple[IdeaItem, ...]:
        clauses = ["i.owner_id=?", "m.status != 'deleted'"]
        params: list[object] = [owner_id]
        if stages:
            clauses.append(f"i.stage IN ({','.join('?' for _ in stages)})")
            params.extend(stage.value for stage in stages)
        if query and query.strip():
            clauses.append("(LOWER(i.title) LIKE ? OR m.normalized_content LIKE ?)")
            pattern = f"%{' '.join(query.split()).casefold()}%"
            params.extend((pattern, pattern))
        params.append(max(1, min(limit, 200)))
        rows = self._connection.execute(
            f"""SELECT i.* FROM idea_items i
            JOIN memory_records m ON m.owner_id=i.owner_id AND m.id=i.memory_id
            WHERE {' AND '.join(clauses)} ORDER BY i.updated_at DESC, i.rowid DESC LIMIT ?""",
            params,
        ).fetchall()
        return tuple(self._item(row) for row in rows)

    def update_stage(
        self,
        owner_id: str,
        idea_id: str,
        *,
        expected_version: int,
        stage: IdeaStage,
    ) -> IdeaItem:
        current = self.get(owner_id, idea_id)
        if current.version != expected_version:
            raise MemoryVersionConflictError("Idea version conflict")
        if stage not in _STAGE_TRANSITIONS[current.stage]:
            raise ValueError(f"Invalid idea transition: {current.stage.value} -> {stage.value}")
        return self._update(
            owner_id,
            idea_id,
            expected_version=expected_version,
            assignments={"stage": stage.value},
            operation=f"stage:{stage.value}",
        )

    def set_next_step(
        self,
        owner_id: str,
        idea_id: str,
        *,
        expected_version: int,
        next_step: str | None,
    ) -> IdeaItem:
        return self._update(
            owner_id,
            idea_id,
            expected_version=expected_version,
            assignments={"next_step": next_step.strip()[:500] if next_step else None},
            operation="set_next_step",
        )

    def link_action(
        self,
        owner_id: str,
        idea_id: str,
        *,
        expected_version: int,
        action_reference: str,
    ) -> IdeaItem:
        if not action_reference.strip():
            raise ValueError("Action reference cannot be empty")
        return self._update(
            owner_id,
            idea_id,
            expected_version=expected_version,
            assignments={"action_reference": action_reference.strip()[:200]},
            operation="link_action",
        )

    def list_for_daily_review(self, owner_id: str, local_day: date) -> tuple[IdeaItem, ...]:
        rows = self._connection.execute(
            """SELECT * FROM idea_items
            WHERE owner_id=? AND substr(created_at, 1, 10)=? AND stage != 'archived'
            ORDER BY created_at, rowid""",
            (owner_id, local_day.isoformat()),
        ).fetchall()
        return tuple(self._item(row) for row in rows)

    def _create_or_existing(
        self,
        *,
        owner_id: str,
        memory_id: str,
        title: str,
        authorization: StorageAuthorization,
        related_goal_memory_id: str | None,
    ) -> IdeaItem:
        existing = self._connection.execute(
            "SELECT * FROM idea_items WHERE owner_id=? AND memory_id=?",
            (owner_id, memory_id),
        ).fetchone()
        if existing is not None:
            return self._item(existing)
        clean_title = " ".join(title.split())
        if not clean_title:
            raise ValueError("Idea title cannot be empty")
        if related_goal_memory_id is not None:
            self.memories.get(owner_id, related_goal_memory_id)
        idea_id = str(uuid4())
        now = _now().isoformat()
        with self._connection:
            self._connection.execute(
                """INSERT INTO idea_items (
                    id, owner_id, memory_id, title, stage, authorization,
                    related_goal_memory_id, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'captured', ?, ?, 1, ?, ?)""",
                (
                    idea_id,
                    owner_id,
                    memory_id,
                    clean_title,
                    authorization.value,
                    related_goal_memory_id,
                    now,
                    now,
                ),
            )
            self._audit(owner_id, idea_id, "create", 1)
        return self.get(owner_id, idea_id)

    def _update(
        self,
        owner_id: str,
        idea_id: str,
        *,
        expected_version: int,
        assignments: dict[str, str | None],
        operation: str,
    ) -> IdeaItem:
        current = self.get(owner_id, idea_id)
        if current.version != expected_version:
            raise MemoryVersionConflictError("Idea version conflict")
        allowed = {"stage", "next_step", "action_reference", "last_reviewed_at"}
        if not assignments or not set(assignments) <= allowed:
            raise ValueError("Unsupported or empty idea update")
        version = expected_version + 1
        now = _now().isoformat()
        columns = ", ".join(f"{key}=?" for key in assignments)
        params = [*assignments.values(), version, now, owner_id, idea_id, expected_version]
        with self._connection:
            cursor = self._connection.execute(
                f"""UPDATE idea_items SET {columns}, version=?, updated_at=?
                WHERE owner_id=? AND id=? AND version=?""",
                params,
            )
            if cursor.rowcount != 1:
                raise MemoryVersionConflictError("Idea version conflict")
            self._audit(owner_id, idea_id, operation, version)
        return self.get(owner_id, idea_id)

    def _audit(self, owner_id: str, idea_id: str, operation: str, version: int) -> None:
        self._connection.execute(
            "INSERT INTO idea_audit_events VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid4()), owner_id, idea_id, operation, version, _now().isoformat()),
        )

    @staticmethod
    def _item(row: sqlite3.Row) -> IdeaItem:
        return IdeaItem(
            id=row["id"],
            owner_id=row["owner_id"],
            memory_id=row["memory_id"],
            title=row["title"],
            stage=IdeaStage(row["stage"]),
            authorization=StorageAuthorization(row["authorization"]),
            related_goal_memory_id=row["related_goal_memory_id"],
            next_step=row["next_step"],
            action_reference=row["action_reference"],
            version=row["version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_reviewed_at=(
                datetime.fromisoformat(row["last_reviewed_at"])
                if row["last_reviewed_at"]
                else None
            ),
        )
