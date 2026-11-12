from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class MemoryStoreError(RuntimeError):
    """Raised when a long-term memory provider cannot complete an operation."""


class MemoryRetrievalMode(StrEnum):
    PLANNING = "planning"
    COMPANION = "companion"


@dataclass(frozen=True, slots=True)
class MemoryItem:
    id: str | None
    content: str
    kind: str
    relevance: float | None = None
    confidence: str | None = None
    source: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryContext:
    facts: tuple[MemoryItem, ...] = ()
    preferences: tuple[MemoryItem, ...] = ()


class MemoryStore(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def search(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
        mode: MemoryRetrievalMode = MemoryRetrievalMode.PLANNING,
    ) -> MemoryContext: ...

    async def write_claim(
        self,
        *,
        user_id: str,
        conversation_id: str,
        local_memory_id: str,
        content: str,
        memory_type: str,
    ) -> None: ...

    async def list_memories(
        self, user_id: str, *, local_memory_id: str | None = None
    ) -> MemoryContext: ...

    async def delete_memories(self, user_id: str, memory_ids: tuple[str, ...]) -> None: ...


class DisabledMemoryStore:
    """No-network auxiliary provider used when MemOS is not configured."""

    async def search(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
        mode: MemoryRetrievalMode = MemoryRetrievalMode.PLANNING,
    ) -> MemoryContext:
        del user_id, conversation_id, query, mode
        return MemoryContext()

    async def write_claim(
        self,
        *,
        user_id: str,
        conversation_id: str,
        local_memory_id: str,
        content: str,
        memory_type: str,
    ) -> None:
        del user_id, conversation_id, local_memory_id, content, memory_type

    async def list_memories(
        self, user_id: str, *, local_memory_id: str | None = None
    ) -> MemoryContext:
        del user_id, local_memory_id
        return MemoryContext()

    async def delete_memories(self, user_id: str, memory_ids: tuple[str, ...]) -> None:
        del user_id, memory_ids

    async def aclose(self) -> None:
        return None
    @property
    def enabled(self) -> bool:
        return False
