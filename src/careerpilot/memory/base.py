from dataclasses import dataclass
from typing import Protocol


class MemoryStoreError(RuntimeError):
    """Raised when a long-term memory provider cannot complete an operation."""


@dataclass(frozen=True, slots=True)
class MemoryItem:
    id: str | None
    content: str
    kind: str
    relevance: float | None = None


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
    ) -> MemoryContext: ...

    async def add_turn(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None: ...

