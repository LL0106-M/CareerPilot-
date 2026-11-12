from dataclasses import dataclass

import pytest

from careerpilot.harness.contracts import ModelRequest, ModelResponse
from careerpilot.memory.base import MemoryContext
from careerpilot.memory.dreaming import DreamingSnapshot, DreamingTrigger
from careerpilot.memory.dreaming_llm import JsonDreamingAnalyzer


@dataclass
class AIMessage:
    content: str


class FakeMessagesListChatModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = list(responses)
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(text=self.responses.pop(0).content)

def snapshot() -> DreamingSnapshot:
    return DreamingSnapshot.from_turn(
        user_id="u1",
        conversation_id="c1",
        trigger=DreamingTrigger.MANUAL_REVIEW,
        user_message="帮我复盘",
        assistant_message="好",
        memories=MemoryContext(),
    )


@pytest.mark.asyncio
async def test_analyzer_parses_evidence_bound_candidate_json() -> None:
    evidence_id = snapshot().evidence[0].id
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content=(
                    '{"hypotheses":[{"statement":"用户可能重视稳定",'
                    '"confidence_band":"low","supporting_evidence_ids":["'
                    + evidence_id
                    + '"],"contradicting_evidence_ids":[],"open_questions":[]}]}'
                )
            )
        ]
    )

    proposals = await JsonDreamingAnalyzer(model).analyze(snapshot())

    assert proposals[0].statement == "用户可能重视稳定"
    assert proposals[0].supporting_evidence_ids == (evidence_id,)


@pytest.mark.asyncio
async def test_analyzer_rejects_non_object_json() -> None:
    model = FakeMessagesListChatModel(responses=[AIMessage(content="[]")])

    with pytest.raises(ValueError, match="JSON object"):
        await JsonDreamingAnalyzer(model).analyze(snapshot())

