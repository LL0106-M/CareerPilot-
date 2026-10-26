from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from math import sqrt
from typing import Protocol

from careerpilot.memory.models import (
    MemoryConfidence,
    MemoryOrigin,
    MemoryRecord,
    MemorySensitivity,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
    MemoryUsageType,
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
    relevance: dict[str, float] = field(default_factory=dict)


class MemoryEmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class MemoryService:
    def __init__(
        self,
        store: SqliteUnifiedMemoryStore,
        embedder: MemoryEmbeddingProvider | None = None,
    ) -> None:
        self.store = store
        self._embedder = embedder

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
        self._index(record)
        return record

    def remember_from_conversation(
        self,
        *,
        owner_id: str,
        memory_type: MemoryType,
        content: str,
        sensitivity: MemorySensitivity,
        importance: int,
        source_reference: str,
        correction: bool = False,
    ) -> MemoryRecord:
        """Persist an explicit user statement and retire a clearly corrected value."""

        previous = self.store.list_active_memories(owner_id, limit=200)
        record = self.create_explicit(
            owner_id=owner_id,
            memory_type=memory_type,
            content=content,
            sensitivity=sensitivity,
            importance=importance,
            source_type=MemorySourceType.CONVERSATION,
            source_reference=source_reference,
        )
        if not correction or record.status is not MemoryStatus.ACTIVE:
            return record
        new_tokens = set(_lexical_tokens(record.content))
        for old in previous:
            if old.id == record.id or old.type is not memory_type:
                continue
            if not new_tokens.intersection(_lexical_tokens(old.content)):
                continue
            self.store.transition_memory(
                owner_id,
                old.id,
                expected_version=old.version,
                target=MemoryStatus.SUPERSEDED,
                actor_kind="user",
            )
            self.store.add_relation(owner_id, record.id, old.id, "supersedes")
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
        self._index(record)
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
        updated = self.store.update_memory(
            owner_id, memory_id, expected_version=expected_version, **changes
        )
        if "content" in changes:
            self._index(updated)
        return updated

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
        broad_recall: bool = False,
    ) -> MemoryContextBundle:
        tokens = _lexical_tokens(query)
        query_cjk = "".join(re.findall(r"[\u4e00-\u9fff]", query))
        query_bigrams = {query_cjk[index : index + 2] for index in range(len(query_cjk) - 1)}
        active = self.store.list_active_memories(owner_id, limit=200)
        vectors = self.store.get_embeddings(owner_id, tuple(item.id for item in active))
        query_vector = self._embed_query(query) if vectors else None
        ranked: list[tuple[float, MemoryRecord]] = []
        for record in active:
            if record.sensitivity is MemorySensitivity.SENSITIVE and (
                not explicit_personal_recall or purpose is MemoryQueryPurpose.ACTION_PREVIEW
            ):
                continue
            content = record.content.casefold()
            content_tokens = _lexical_tokens(content)
            overlap = len(set(tokens) & set(content_tokens))
            score = float(overlap * 3)
            content_cjk = "".join(re.findall(r"[\u4e00-\u9fff]", content))
            content_bigrams = {
                content_cjk[index : index + 2] for index in range(len(content_cjk) - 1)
            }
            bigram_overlap = len(query_bigrams & content_bigrams)
            score += min(8, bigram_overlap) * 1.25
            dense_score = _cosine(query_vector, vectors.get(record.id))
            if dense_score is not None:
                score += max(0.0, dense_score) * 8
            lexical_match = overlap > 0 or bigram_overlap > 0 or query.casefold() in content
            semantic_match = dense_score is not None and dense_score >= 0.35
            if query.strip() and not broad_recall and not (
                lexical_match or semantic_match
            ):
                continue
            score += record.importance * 0.7
            score += {MemoryConfidence.HIGH: 1.5, MemoryConfidence.MEDIUM: 0.75}.get(
                record.confidence, 0
            )
            score += _purpose_weight(purpose, record.type)
            score += _recency_weight(record.updated_at)
            ranked.append((score, record))
        ranked.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        selected = ranked[: max(1, min(limit, 20))]
        return MemoryContextBundle(
            tuple(record for _, record in selected),
            {record.id: round(score, 4) for score, record in selected},
        )

    def record_context_usage(
        self,
        owner_id: str,
        records: tuple[MemoryRecord, ...],
        *,
        turn_id: str,
        purpose: MemoryQueryPurpose,
    ) -> None:
        usage_type = (
            MemoryUsageType.ACTION_PREVIEW
            if purpose is MemoryQueryPurpose.ACTION_PREVIEW
            else MemoryUsageType.ANSWER_CONTEXT
        )
        for record in records:
            self.store.record_usage(
                owner_id,
                record.id,
                turn_id=turn_id,
                usage_type=usage_type,
                result_reference="context_compiler",
            )

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

    def _index(self, record: MemoryRecord) -> None:
        if self._embedder is None:
            return
        try:
            vectors = self._embedder.embed_documents([record.content])
            if vectors and vectors[0]:
                self.store.upsert_embedding(record.owner_id, record.id, vectors[0])
        except Exception:
            # Dense recall is optional. Lexical recall must remain available when the
            # embedding provider is temporarily unavailable.
            return

    def _embed_query(self, query: str) -> tuple[float, ...] | None:
        if self._embedder is None:
            return None
        try:
            vector = self._embedder.embed_query(query)
            return tuple(vector) if vector else None
        except Exception:
            return None


def _lexical_tokens(text: str) -> tuple[str, ...]:
    latin = tuple(re.findall(r"[a-z0-9_+#.-]+", text.casefold()))
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    cjk_bigrams = tuple(cjk[index : index + 2] for index in range(len(cjk) - 1))
    return tuple(dict.fromkeys((*latin, *cjk_bigrams)))


def _cosine(
    left: tuple[float, ...] | None, right: tuple[float, ...] | None
) -> float | None:
    if left is None or right is None or len(left) != len(right) or not left:
        return None
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return None
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _purpose_weight(purpose: MemoryQueryPurpose, memory_type: MemoryType) -> float:
    preferred = {
        MemoryQueryPurpose.COMPANION: {
            MemoryType.PREFERENCE,
            MemoryType.FACT,
            MemoryType.EXPERIENCE,
        },
        MemoryQueryPurpose.PLANNING: {
            MemoryType.GOAL,
            MemoryType.CONSTRAINT,
            MemoryType.DECISION,
            MemoryType.PREFERENCE,
        },
        MemoryQueryPurpose.REVIEW: {
            MemoryType.EXPERIENCE,
            MemoryType.DECISION,
            MemoryType.GOAL,
        },
        MemoryQueryPurpose.ACTION_PREVIEW: {
            MemoryType.CONSTRAINT,
            MemoryType.DECISION,
            MemoryType.PREFERENCE,
        },
    }
    return 1.5 if memory_type in preferred[purpose] else 0.0


def _recency_weight(updated_at: datetime) -> float:
    age_days = max(0, (datetime.now(UTC) - updated_at.astimezone(UTC)).days)
    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.4
    return 0.0
