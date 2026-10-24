from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

from careerpilot.memory.models import (
    MemoryConfidence,
    MemoryOrigin,
    MemoryRecord,
    MemorySensitivity,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)
from careerpilot.memory.unified_store import MemoryVersionConflictError, SqliteUnifiedMemoryStore


class MemoryQueryPurpose(StrEnum):
    COMPANION = "companion"
    PLANNING = "planning"
    REVIEW = "review"
    ACTION_PREVIEW = "action_preview"


@dataclass(frozen=True, slots=True)
class MemoryContextBundle:
    records: tuple[MemoryRecord, ...]


class MemoryService:
    def __init__(self, store: SqliteUnifiedMemoryStore) -> None:
        self.store = store

    def create_explicit(
        self,
        *,
        owner_id: str,
        memory_type: MemoryType,
        content: str,
        sensitivity: MemorySensitivity = MemorySensitivity.NORMAL,
        importance: int = 3,
        source_type: MemorySourceType = MemorySourceType.MANUAL,
        source_reference: str | None = None,
    ) -> MemoryRecord:
        status = (
            MemoryStatus.CANDIDATE
            if sensitivity is MemorySensitivity.SENSITIVE
            else MemoryStatus.ACTIVE
        )
        existing = self._find_duplicate(owner_id, memory_type, content)
        if existing is not None:
            self._add_statement_evidence(existing, source_reference, content)
            return existing
        record = self.store.create_memory(
            owner_id=owner_id,
            memory_type=memory_type,
            content=content,
            status=status,
            sensitivity=sensitivity,
            origin=MemoryOrigin.USER_EXPLICIT,
            source_type=source_type,
            source_reference=source_reference,
            confidence=MemoryConfidence.HIGH,
            importance=importance,
            actor_kind="user",
        )
        self._add_statement_evidence(record, source_reference, content)
        return record

    def propose(
        self,
        *,
        owner_id: str,
        memory_type: MemoryType,
        content: str,
        origin: MemoryOrigin,
        source_type: MemorySourceType,
        source_reference: str | None = None,
        sensitivity: MemorySensitivity = MemorySensitivity.NORMAL,
        confidence: MemoryConfidence = MemoryConfidence.MEDIUM,
        importance: int = 3,
        contradicts_memory_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> MemoryRecord:
        existing = self._find_duplicate(owner_id, memory_type, content)
        if existing is not None:
            self._add_statement_evidence(existing, source_reference, content)
            return existing
        record = self.store.create_memory(
            owner_id=owner_id,
            memory_type=memory_type,
            content=content,
            status=MemoryStatus.CANDIDATE,
            sensitivity=sensitivity,
            origin=origin,
            source_type=source_type,
            source_reference=source_reference,
            confidence=confidence,
            importance=importance,
            metadata=metadata,
            actor_kind="agent" if origin is MemoryOrigin.AGENT_EXTRACTED else "system",
        )
        self._add_statement_evidence(record, source_reference, content)
        if contradicts_memory_id is not None:
            self.store.add_relation(owner_id, record.id, contradicts_memory_id, "contradicts")
        return record

    def get(self, owner_id: str, memory_id: str) -> MemoryRecord:
        return self.store.get_memory(owner_id, memory_id)

    def update(
        self,
        owner_id: str,
        memory_id: str,
        *,
        expected_version: int,
        **changes: object,
    ) -> MemoryRecord:
        current = self.get(owner_id, memory_id)
        if current.version != expected_version:
            raise MemoryVersionConflictError("Memory version conflict")
        sensitivity = changes.get("sensitivity", current.sensitivity)
        if (
            current.status is MemoryStatus.ACTIVE
            and sensitivity is MemorySensitivity.SENSITIVE
            and current.sensitivity is not MemorySensitivity.SENSITIVE
        ):
            replacement = self.propose(
                owner_id=owner_id,
                memory_type=changes.get("type", current.type),
                content=str(changes.get("content", current.content)),
                origin=MemoryOrigin.USER_EXPLICIT,
                source_type=current.source_type,
                source_reference=current.source_reference,
                sensitivity=MemorySensitivity.SENSITIVE,
                confidence=changes.get("confidence", current.confidence),
                importance=int(changes.get("importance", current.importance)),
                metadata=current.metadata,
            )
            self.store.add_relation(owner_id, replacement.id, current.id, "supersedes")
            return replacement
        return self.store.update_memory(
            owner_id, memory_id, expected_version=expected_version, **changes
        )

    def list(
        self,
        owner_id: str,
        *,
        statuses: tuple[MemoryStatus, ...] | None = None,
        types: tuple[MemoryType, ...] | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> tuple[MemoryRecord, ...]:
        return self.store.list_memories(
            owner_id, statuses=statuses, types=types, query=query, limit=limit
        )

    def confirm(self, owner_id: str, memory_id: str, *, expected_version: int) -> MemoryRecord:
        return self.store.transition_memory(
            owner_id,
            memory_id,
            expected_version=expected_version,
            target=MemoryStatus.ACTIVE,
            actor_kind="user",
        )

    def pause(self, owner_id: str, memory_id: str, *, expected_version: int) -> MemoryRecord:
        return self.store.transition_memory(
            owner_id,
            memory_id,
            expected_version=expected_version,
            target=MemoryStatus.PAUSED,
            actor_kind="user",
        )

    def resume(self, owner_id: str, memory_id: str, *, expected_version: int) -> MemoryRecord:
        return self.store.transition_memory(
            owner_id,
            memory_id,
            expected_version=expected_version,
            target=MemoryStatus.ACTIVE,
            actor_kind="user",
        )

    def delete(self, owner_id: str, memory_id: str, *, expected_version: int) -> MemoryRecord:
        return self.store.transition_memory(
            owner_id,
            memory_id,
            expected_version=expected_version,
            target=MemoryStatus.DELETED,
            actor_kind="user",
        )

    def search_context(
        self,
        *,
        owner_id: str,
        query: str,
        purpose: MemoryQueryPurpose,
        limit: int = 8,
        explicit_personal_recall: bool = False,
    ) -> MemoryContextBundle:
        tokens = tuple(token.casefold() for token in query.split() if token.strip())
        query_cjk = "".join(re.findall(r"[\u4e00-\u9fff]", query))
        query_bigrams = {query_cjk[index : index + 2] for index in range(len(query_cjk) - 1)}
        ranked: list[tuple[int, MemoryRecord]] = []
        for record in self.store.list_active_memories(owner_id, limit=200):
            if record.sensitivity is MemorySensitivity.SENSITIVE and (
                not explicit_personal_recall or purpose is MemoryQueryPurpose.ACTION_PREVIEW
            ):
                continue
            content = record.content.casefold()
            score = sum(5 for token in tokens if token in content)
            content_cjk = "".join(re.findall(r"[\u4e00-\u9fff]", content))
            content_bigrams = {
                content_cjk[index : index + 2] for index in range(len(content_cjk) - 1)
            }
            score += len(query_bigrams & content_bigrams) * 2
            if query.strip() and score == 0 and query.casefold() not in content:
                continue
            score += record.importance
            score += {MemoryConfidence.HIGH: 2, MemoryConfidence.MEDIUM: 1}.get(
                record.confidence, 0
            )
            ranked.append((score, record))
        ranked.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return MemoryContextBundle(tuple(record for _, record in ranked[: max(1, min(limit, 20))]))

    def _find_duplicate(
        self, owner_id: str, memory_type: MemoryType, content: str
    ) -> MemoryRecord | None:
        normalized = " ".join(content.split()).casefold()
        for record in self.store.list_memories(owner_id, types=(memory_type,), limit=200):
            if record.content.casefold() == normalized:
                return record
        return None

    def _add_statement_evidence(
        self, record: MemoryRecord, source_reference: str | None, content: str
    ) -> None:
        self.store.add_evidence(
            record.owner_id,
            record.id,
            kind="user_statement",
            source_reference=source_reference,
            excerpt=content,
        )
