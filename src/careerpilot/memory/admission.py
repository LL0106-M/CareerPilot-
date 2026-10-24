from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from careerpilot.memory.models import MemorySensitivity, MemoryType


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    type: MemoryType
    content: str
    sensitivity: MemorySensitivity = MemorySensitivity.NORMAL


class MemoryExtractor(Protocol):
    async def extract(self, user_message: str, assistant_message: str) -> tuple[MemoryProposal, ...]: ...


class MemoryAdmissionPolicy(Protocol):
    def should_extract(self, user_message: str, assistant_message: str) -> bool: ...
