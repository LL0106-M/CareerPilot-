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
    async def search(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
        mode: MemoryRetrievalMode = MemoryRetrievalMode.PLANNING,
    ) -> MemoryContext: ...

    async def add_turn(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None: ...


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

    async def add_turn(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        del user_id, conversation_id, user_message, assistant_message

    async def aclose(self) -> None:
        return None
