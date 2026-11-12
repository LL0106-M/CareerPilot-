import json

import pytest

from careerpilot.harness.contracts import ModelResponse
from careerpilot.memory.contracts import MemoryAuthorship, MemorySubject
from careerpilot.memory.extractor import (
    MemoryExtractionTurn,
    ModelMemoryClaimExtractor,
    RuleBasedMemoryClaimExtractor,
)
from careerpilot.memory.models import MemoryType


class FakeModel:
    def __init__(self, text: str) -> None:
        self.text = text
        self.requests = []

    async def generate(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return ModelResponse(text=self.text)


@pytest.mark.asyncio
async def test_rule_based_extractor_emits_typed_self_claim_with_bound_evidence() -> None:
    turn = MemoryExtractionTurn(
        turn_id="turn-1",
        user_message="我长期更看重稳定的工作节奏。",
        assistant_message="了解。",
    )

    claims = await RuleBasedMemoryClaimExtractor().extract(turn)

    assert len(claims) == 1
    assert claims[0].memory_type is MemoryType.PREFERENCE
    assert claims[0].subject is MemorySubject.SELF
    assert claims[0].authorship is MemoryAuthorship.USER_EXPLICIT
    assert claims[0].evidence[0].message_id == "turn-1:user"
    assert claims[0].evidence[0].excerpt in turn.user_message


@pytest.mark.asyncio
async def test_model_extractor_validates_structured_json_and_treats_chat_as_untrusted() -> None:
    payload = {
        "claims": [
            {
                "content": "我长期更看重稳定的工作节奏",
                "memory_type": "preference",
                "cognitive_class": "semantic",
                "subject": "self",
                "authorship": "user_explicit",
                "evidence": [{"excerpt": "我长期更看重稳定的工作节奏"}],
                "durability": "durable",
                "sensitivity": "normal",
                "confidence": "high",
            }
        ]
    }
    model = FakeModel(json.dumps(payload, ensure_ascii=False))
    extractor = ModelMemoryClaimExtractor(model)
    turn = MemoryExtractionTurn("turn-2", "我长期更看重稳定的工作节奏", "收到")

    claims = await extractor.extract(turn)

    assert len(claims) == 1
    assert claims[0].evidence[0].message_id == "turn-2:user"
    system_prompt = model.requests[0].messages[0].content
    assert "不可信" in system_prompt
    assert "指令" in system_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("model_text", ["not-json", "{}", '{"claims": "bad"}'])
async def test_model_extractor_returns_no_claims_for_malformed_output(model_text: str) -> None:
    claims = await ModelMemoryClaimExtractor(FakeModel(model_text)).extract(
        MemoryExtractionTurn("turn-3", "我长期喜欢远程工作", "收到")
    )

    assert claims == ()


@pytest.mark.asyncio
async def test_model_extractor_rejects_evidence_not_present_in_user_message() -> None:
    payload = {
        "claims": [
            {
                "content": "用户是完美主义者",
                "memory_type": "hypothesis",
                "cognitive_class": "semantic",
                "subject": "self",
                "authorship": "agent_inferred",
                "evidence": [{"excerpt": "用户是完美主义者"}],
                "durability": "durable",
                "sensitivity": "normal",
                "confidence": "medium",
            }
        ]
    }

    claims = await ModelMemoryClaimExtractor(
        FakeModel(json.dumps(payload, ensure_ascii=False))
    ).extract(MemoryExtractionTurn("turn-4", "我今天改了三次简历", "你可能要求很高"))

    assert claims == ()
