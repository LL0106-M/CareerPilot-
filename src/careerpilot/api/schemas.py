from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from careerpilot.context.contracts import RetrievalSource, TaskIntent
from careerpilot.memory.ideas import IdeaStage, StorageAuthorization
from careerpilot.memory.models import MemoryConfidence, MemorySensitivity, MemoryType
from careerpilot.support.policy import SupportMode


class VerificationCodeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: str = Field(
        min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )


class RegisterRequest(VerificationCodeRequest):
    username: str = Field(min_length=3, max_length=40)
    verification_code: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    remember_me: bool = False


class ChatRequest(BaseModel):
    """Client request. ``user_id`` was removed in v0.2 because it must
    not be trusted from the client — the server derives ``owner_id``
    from an HttpOnly cookie. ``conversation_id`` is optional; when
    omitted the server issues one for the current session."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    conversation_id: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=1, max_length=8_000)
    support_mode: SupportMode | None = None


class DirectionSignalResponse(BaseModel):
    id: str
    label: str
    explicitness: Literal["implicit", "explicit"]
    source_quote: str
    reason: str
    confidence: float
    suggested_action: Literal["ask_to_add", "add_to_compass"]
    status: Literal["pending", "accepted"]
    signal_kind: Literal["direction", "target"] = "direction"
    company: str | None = None
    business: str | None = None
    role: str | None = None
    location: str | None = None
    constraints: tuple[str, ...] = ()


class CompassItemCorrectionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    value: str = Field(min_length=1, max_length=500)


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
    memory_provider_status: str = "skipped"
    dreaming_status: str
    memory_ids: tuple[str, ...] = ()
    direction_signal: DirectionSignalResponse | None = None
    compass_update_batch: dict[str, Any] | None = None


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


class FutureLetterCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(default="两年后的我会怎样？", min_length=1, max_length=1_000)


class FutureTakeawayCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    letter_id: str = Field(min_length=1, max_length=128)
    path_kind: Literal["continue", "adjacent", "unexpected"]
    question: str = Field(min_length=1, max_length=500)


class JourneyCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    start_at: datetime
    end_at: datetime | None = None
    reminder_minutes: int | None = Field(default=None, ge=0, le=43_200)
    meeting_url: str | None = Field(default=None, max_length=2_000)
    notes: str | None = Field(default=None, max_length=2_000)
    related: str = Field(default="个人日程", min_length=1, max_length=240)

    @field_validator("meeting_url")
    @classmethod
    def validate_meeting_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("meeting_url must be an HTTPS URL")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> "JourneyCreateRequest":
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self


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
