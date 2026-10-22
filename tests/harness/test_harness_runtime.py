from dataclasses import dataclass, field

import pytest

from careerpilot.harness.contracts import ModelRequest, ModelResponse, ToolCall
from careerpilot.harness.runtime import CareerPilotHarness, MaxStepsExceeded
from careerpilot.harness.session import InMemorySessionStore


@dataclass
class RecordingGateway:
    responses: list[ModelResponse]
    requests: list[ModelRequest] = field(default_factory=list)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_harness_replays_session_history_on_next_turn() -> None:
    gateway = RecordingGateway(
        [ModelResponse(text="第一轮"), ModelResponse(text="第二轮")]
    )
    sessions = InMemorySessionStore()
    harness = CareerPilotHarness(gateway, session_store=sessions)

    await harness.run(
        user_message="你好", system_context="system-v1", session_id="s1"
    )
    await harness.run(
        user_message="继续", system_context="system-v2", session_id="s1"
    )

    second_messages = gateway.requests[1].messages
    assert [item.role for item in second_messages] == ["system", "user", "assistant", "user"]
    assert second_messages[0].content == "system-v2"
    assert second_messages[1].content == "你好"
    assert second_messages[2].content == "第一轮"


@pytest.mark.asyncio
async def test_harness_returns_forbidden_result_for_disallowed_call() -> None:
    gateway = RecordingGateway(
        [
            ModelResponse(
                tool_calls=(ToolCall("call-1", "search", {"query": "x"}),)
            ),
            ModelResponse(text="我不会执行该工具。"),
        ]
    )
    harness = CareerPilotHarness(gateway)

    result = await harness.run(
        user_message="只听我说",
        system_context="listen",
        session_id="s1",
        allowed_tool_names=frozenset(),
    )

    assert result.reply == "我不会执行该工具。"
    tool_message = gateway.requests[1].messages[-1]
    assert tool_message.role == "tool"
    assert '"status": "forbidden"' in tool_message.content


@pytest.mark.asyncio
async def test_harness_stops_runaway_model() -> None:
    gateway = RecordingGateway(
        [
            ModelResponse(tool_calls=(ToolCall(f"c{i}", "missing", {}),))
            for i in range(2)
        ]
    )
    harness = CareerPilotHarness(gateway, max_steps=2)

    with pytest.raises(MaxStepsExceeded):
        await harness.run(
            user_message="循环", system_context="test", session_id="s1"
        )
