from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from careerpilot.support.policy import SupportDecision, SupportMode


class TaskIntent(StrEnum):
    EMOTIONAL_SUPPORT = "emotional_support"
    CAREER_DIRECTION = "career_direction"
    JOB_DISCOVERY = "job_discovery"
    JOB_COMPARISON = "job_comparison"
    RESUME_REVIEW = "resume_review"
    RESUME_TAILORING = "resume_tailoring"
    INTERVIEW_PREPARATION = "interview_preparation"
    INTERVIEW_REVIEW = "interview_review"
    OFFER_DECISION = "offer_decision"
    CAREER_PLANNING = "career_planning"
    PROFILE_UPDATE = "profile_update"
    GENERAL_QUESTION = "general_question"


class IntentConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class IntentSlot:
    name: str
    values: tuple[str, ...]
    source: str = "current_message"
    confidence: IntentConfidence = IntentConfidence.HIGH
    scope: str = "current_task"


@dataclass(frozen=True, slots=True)
class IntentFrame:
    support: SupportDecision
    primary_intent: TaskIntent
    secondary_intents: tuple[TaskIntent, ...] = ()
    slots: tuple[IntentSlot, ...] = ()
    confidence: IntentConfidence = IntentConfidence.MEDIUM
    reason_codes: tuple[str, ...] = ()
    forbids_memory: bool = False

    @property
    def support_mode(self) -> SupportMode:
        return self.support.mode

    def slot(self, name: str) -> IntentSlot | None:
        return next((item for item in self.slots if item.name == name), None)


class RetrievalSource(StrEnum):
    MEMORY = "memory"
    COGNITIVE_STATE = "cognitive_state"
    PRIVATE_DOCUMENTS = "private_documents"
    CAREER_KNOWLEDGE = "career_knowledge"
    JOBS = "jobs"
    WEB = "web"


@dataclass(frozen=True, slots=True)
class RetrievalRoute:
    source: RetrievalSource
    purpose: str
    required: bool = False
    freshness: str = "normal"
    online_allowed: bool = False


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    routes: tuple[RetrievalRoute, ...] = ()
    allowed_tool_names: frozenset[str] = frozenset()
    reason_codes: tuple[str, ...] = ()

    def uses(self, source: RetrievalSource) -> bool:
        return any(route.source is source for route in self.routes)

    def route_for(self, source: RetrievalSource) -> RetrievalRoute | None:
        return next((route for route in self.routes if route.source is source), None)


class IntentInterpreter(Protocol):
    async def interpret(
        self,
        message: str,
        requested_mode: SupportMode | None = None,
    ) -> IntentFrame: ...


class RetrievalRouter(Protocol):
    def plan(self, frame: IntentFrame, message: str) -> RetrievalPlan: ...
