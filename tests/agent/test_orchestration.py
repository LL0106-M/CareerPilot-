from careerpilot.agent.base import AgentResponse
from careerpilot.agent.orchestration import AgentPlan, AgentVerifier
from careerpilot.context.contracts import TaskIntent


def test_verifier_marks_citation_failure_as_partial() -> None:
    plan = AgentPlan(
        objective="answer",
        intent=TaskIntent.GENERAL_QUESTION,
        context_sources=("career_knowledge",),
        allowed_tools=("search_career_knowledge",),
    )

    result = AgentVerifier().verify(
        AgentResponse(
            reply="结论",
            run_id="run-1",
            citation_warnings=("missing_citations",),
        ),
        plan,
    )

    assert result.status == "partial"
    assert result.failed_criteria == ("valid_citations",)
    assert result.retry_recommended is False
