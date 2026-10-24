from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class MemoryType(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    GOAL = "goal"
    CONSTRAINT = "constraint"
    IDEA = "idea"
    EXPERIENCE = "experience"
    DECISION = "decision"
    HYPOTHESIS = "hypothesis"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    PAUSED = "paused"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


class MemorySensitivity(StrEnum):
    NORMAL = "normal"
    PRIVATE = "private"
    SENSITIVE = "sensitive"


class MemoryOrigin(StrEnum):
    USER_EXPLICIT = "user_explicit"
    AGENT_EXTRACTED = "agent_extracted"
    DREAMING = "dreaming"
    IMPORTED = "imported"


class MemorySourceType(StrEnum):
    CONVERSATION = "conversation"
    MANUAL = "manual"
    INTEGRATION = "integration"
    DREAMING = "dreaming"
    MIGRATION = "migration"


class MemoryConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MemoryUsageType(StrEnum):
    ANSWER_CONTEXT = "answer_context"
    RETRIEVAL_FILTER = "retrieval_filter"
    ACTION_SUGGESTION = "action_suggestion"
    ACTION_PREVIEW = "action_preview"
    GOAL_UPDATE = "goal_update"
    CONFLICT_DETECTED = "conflict_detected"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: str
    owner_id: str
    type: MemoryType
    content: str
    status: MemoryStatus
    sensitivity: MemorySensitivity
    origin: MemoryOrigin
    source_type: MemorySourceType
    source_reference: str | None
    confidence: MemoryConfidence
    importance: int
    version: int
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    deleted_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryEvidence:
    id: str
    memory_id: str
    owner_id: str
    kind: str
    source_reference: str | None
    excerpt: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryUsage:
    id: str
    memory_id: str
    owner_id: str
    turn_id: str
    usage_type: MemoryUsageType
    result_reference: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryRevision:
    id: str
    memory_id: str
    owner_id: str
    from_version: int
    to_version: int
    before: dict[str, Any]
    after: dict[str, Any]
    created_at: datetime
