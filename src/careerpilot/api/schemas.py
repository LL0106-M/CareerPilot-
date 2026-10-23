from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    reply: str
    support_mode: SupportMode
    memory_read_status: str
    memory_write_status: str
    dreaming_status: str


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
