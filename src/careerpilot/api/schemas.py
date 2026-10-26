from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from careerpilot.context.contracts import RetrievalSource, TaskIntent
from careerpilot.memory.ideas import IdeaStage, StorageAuthorization
from careerpilot.memory.models import MemoryConfidence, MemorySensitivity, MemoryType
from careerpilot.support.policy import SupportMode


class ChatRequest(BaseModel):
    """Client request. ``user_id`` was removed in v0.2 because it must
    not be trusted from the client — the server derives ``owner_id``
    from an HttpOnly cookie. ``conversation_id`` is optional; when
    omitted the server issues one for the current session."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    conversation_id: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=1, max_length=8_000)
    support_mode: SupportMode | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    run_id: str
    result_status: Literal["completed", "partial", "blocked", "failed", "cancelled"]
    citation_ids: tuple[str, ...] = ()
    citation_warnings: tuple[str, ...] = ()
    reply: str
    support_mode: SupportMode
    primary_intent: TaskIntent
    retrieval_sources: tuple[RetrievalSource, ...]
    memory_read_status: str
    memory_write_status: str
    dreaming_status: str
    memory_ids: tuple[str, ...] = ()


class AgentRunResponse(BaseModel):
    run_id: str
    conversation_id: str
    status: str
    stage: str
    runtime_phase: str | None = None
    step: int
    version: int
    cancellation_requested: bool
    result: dict[str, Any]
    error: dict[str, Any]
    created_at: str
    updated_at: str


class RunEventResponse(BaseModel):
    sequence: int
    event_type: str
    stage: str | None = None
    runtime_phase: str | None = None
    step: int
    data: dict[str, Any]
    created_at: str


class RunEventsResponse(BaseModel):
    items: tuple[RunEventResponse, ...]


class RagQueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=8_000)
    scopes: list[Literal["jobs", "preparation", "personal"]] | None = None
    sub_queries: list[str] = Field(default_factory=list, max_length=8)
    requires_freshness: bool = False
    minimum_sources: int = Field(default=1, ge=1, le=10)
    limit: int = Field(default=5, ge=1, le=20)


class HypothesisDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(confirm|uncertain)$")


class JourneyUpdateRequest(BaseModel):
    state: str = Field(pattern="^(准备开始|进行中|已完成)$")
    reflection: str | None = Field(default=None, max_length=2_000)


class IntegrationGrantRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    capabilities: list[str] = Field(min_length=1, max_length=10)
    purpose: str = Field(min_length=1, max_length=200)
    scope_snapshot: list[str] = Field(default_factory=list, max_length=20)
    resource_constraints: dict[str, list[str]] = Field(default_factory=dict)


class ActionPreviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    provider_id: str = Field(min_length=1, max_length=64)
    capability: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]


class ActionConfirmRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    preview_hash: str = Field(min_length=64, max_length=64)


class ActionApplyRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    confirmation_token: str | None = Field(default=None, max_length=256)
    preview_hash: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=128)


class MemoryCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    type: MemoryType
    content: str = Field(min_length=1, max_length=4_000)
    sensitivity: MemorySensitivity = MemorySensitivity.NORMAL
    importance: int = Field(default=3, ge=1, le=5)
    expires_at: str | None = None


class MemoryUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    expected_version: int = Field(ge=1)
    content: str | None = Field(default=None, min_length=1, max_length=4_000)
    type: MemoryType | None = None
    sensitivity: MemorySensitivity | None = None
    confidence: MemoryConfidence | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    expires_at: str | None = None


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class IdeaCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    raw_text: str = Field(min_length=1, max_length=4_000)
    title: str = Field(min_length=1, max_length=200)
    authorization: StorageAuthorization
    sensitivity: MemorySensitivity = MemorySensitivity.NORMAL
    related_goal_memory_id: str | None = Field(default=None, max_length=128)


class IdeaUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    expected_version: int = Field(ge=1)
    next_step: str | None = Field(default=None, max_length=500)


class IdeaStageRequest(VersionRequest):
    stage: IdeaStage


class IdeaActionLinkRequest(VersionRequest):
    action_reference: str = Field(min_length=1, max_length=200)
