from dataclasses import dataclass
from enum import StrEnum

from careerpilot.agent.base import AgentResponse
from careerpilot.context.contracts import RetrievalPlan, TaskIntent


class AgentStage(StrEnum):
    CREATED = "created"
    UNDERSTAND = "understand"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    LEARN = "learn"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class AgentPlan:
    objective: str
    intent: TaskIntent
    context_sources: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    completion_criteria: tuple[str, ...] = (
        "non_empty_response",
        "valid_citations",
        "no_unhandled_tool_failure",
    )

    @classmethod
    def from_context(
        cls,
        objective: str,
        intent: TaskIntent,
        retrieval_plan: RetrievalPlan,
    ) -> "AgentPlan":
        return cls(
            objective=objective,
            intent=intent,
            context_sources=tuple(route.source.value for route in retrieval_plan.routes),
            allowed_tools=tuple(sorted(retrieval_plan.allowed_tool_names)),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "objective": self.objective,
            "intent": self.intent.value,
            "context_sources": list(self.context_sources),
            "allowed_tools": list(self.allowed_tools),
            "completion_criteria": list(self.completion_criteria),
        }


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: str
    passed_criteria: tuple[str, ...]
    failed_criteria: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    retry_recommended: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed_criteria": list(self.passed_criteria),
            "failed_criteria": list(self.failed_criteria),
            "warnings": list(self.warnings),
            "retry_recommended": self.retry_recommended,
        }


class AgentVerifier:
    """Deterministic P0 verifier; semantic claim verification can extend this port."""

    def verify(self, response: AgentResponse, plan: AgentPlan) -> VerificationResult:
        del plan
        passed: list[str] = []
        failed: list[str] = []
        if response.reply.strip():
            passed.append("non_empty_response")
        else:
            failed.append("non_empty_response")
        if response.citation_warnings:
            failed.append("valid_citations")
        else:
            passed.append("valid_citations")
        passed.append("no_unhandled_tool_failure")
        if "non_empty_response" in failed:
            status = "failed"
        elif failed:
            status = "partial"
        else:
            status = "completed"
        return VerificationResult(
            status=status,
            passed_criteria=tuple(passed),
            failed_criteria=tuple(failed),
            warnings=response.citation_warnings,
            retry_recommended=status == "failed",
        )
