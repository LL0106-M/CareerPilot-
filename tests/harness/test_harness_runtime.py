from dataclasses import dataclass, field

import pytest

from careerpilot.harness.contracts import (
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ToolCall,
)
from careerpilot.harness.events import HarnessEventType, RunPhase
from careerpilot.harness.runtime import CareerPilotHarness, MaxStepsExceeded
from careerpilot.harness.session import InMemorySessionStore


@dataclass
class RecordingGateway:
    responses: list[ModelResponse]
    requests: list[ModelRequest] = field(default_factory=list)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return self.responses.pop(0)


@dataclass
class StreamingGateway:
    responses: list[tuple[list[str], ModelResponse]]

    async def stream(self, request: ModelRequest):
        del request
        deltas, response = self.responses.pop(0)
        for delta in deltas:
            yield ModelStreamEvent(text_delta=delta)
        yield ModelStreamEvent(response=response)


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


@pytest.mark.asyncio
async def test_harness_streams_ordered_provider_neutral_events() -> None:
    gateway = StreamingGateway(
        [(["先", "梳理"], ModelResponse(text="先梳理", usage={"output_tokens": 2}))]
    )
    harness = CareerPilotHarness(gateway)

    events = [
        event
        async for event in harness.stream(
            user_message="我有点乱",
            system_context="organize",
            session_id="s1",
            run_id="run-1",
        )
    ]

    assert [event.type for event in events] == [
        HarnessEventType.RUN_STARTED,
        HarnessEventType.MODEL_STARTED,
        HarnessEventType.TEXT_DELTA,
        HarnessEventType.TEXT_DELTA,
        HarnessEventType.MODEL_COMPLETED,
        HarnessEventType.RUN_COMPLETED,
    ]
    assert [event.sequence for event in events] == list(range(1, 7))
    text_deltas = [
        event.data["text"]
        for event in events
        if event.type is HarnessEventType.TEXT_DELTA
    ]
    assert text_deltas == [
        "先",
        "梳理",
    ]
    assert events[-1].phase is RunPhase.COMPLETED
    assert events[-1].run_id == "run-1"
    assert events[-1].data["usage"] == {"output_tokens": 2}


@pytest.mark.asyncio
async def test_harness_emits_tool_lifecycle_between_model_steps() -> None:
    gateway = RecordingGateway(
        [
            ModelResponse(tool_calls=(ToolCall("call-1", "missing", {"query": "x"}),)),
            ModelResponse(text="已降级处理。"),
        ]
    )
    harness = CareerPilotHarness(gateway)

    events = [
        event
        async for event in harness.stream(
            user_message="查一下",
            system_context="test",
            session_id="s1",
        )
    ]

    event_types = [event.type for event in events]
    assert event_types.index(HarnessEventType.TOOL_REQUESTED) < event_types.index(
        HarnessEventType.TOOL_STARTED
    )
    assert event_types.index(HarnessEventType.TOOL_STARTED) < event_types.index(
        HarnessEventType.TOOL_COMPLETED
    )
    assert events[-1].step == 2
    assert events[-1].data["tool_names"] == ["missing"]


@pytest.mark.asyncio
async def test_harness_emits_failure_before_raising() -> None:
    gateway = RecordingGateway([ModelResponse()])
    harness = CareerPilotHarness(gateway)
    events = []

    with pytest.raises(RuntimeError, match="neither text nor tool calls"):
        async for event in harness.stream(
            user_message="hello",
            system_context="test",
            session_id="s1",
        ):
            events.append(event)

    assert events[-1].type is HarnessEventType.RUN_FAILED
    assert events[-1].phase is RunPhase.FAILED
    assert events[-1].data["error_type"] == "RuntimeError"
