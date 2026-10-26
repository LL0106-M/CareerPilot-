import asyncio
from dataclasses import dataclass, field

import pytest

from careerpilot.harness.contracts import (
    HarnessMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ToolCall,
)
from careerpilot.harness.events import HarnessEventType, RunPhase
from careerpilot.harness.run_store import SqliteAgentRunStore
from careerpilot.harness.runtime import (
    CareerPilotHarness,
    MaxStepsExceeded,
    RunCancellationRequested,
)
from careerpilot.harness.session import InMemorySessionStore
from careerpilot.harness.tools import ToolRegistry


@dataclass
class SlowTool:
    @property
    def schema(self):
        from careerpilot.harness.contracts import ToolSchema

        return ToolSchema(name="slow_search", description="slow", parameters={})

    async def execute(self, arguments):
        del arguments
        await asyncio.sleep(0.05)
        return "late"


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
async def test_harness_turns_tool_timeout_into_observation_and_continues() -> None:
    gateway = RecordingGateway(
        [
            ModelResponse(tool_calls=(ToolCall("call-1", "slow_search", {}),)),
            ModelResponse(text="搜索暂时超时，我先说明资料不足。"),
        ]
    )
    harness = CareerPilotHarness(
        gateway,
        tools=ToolRegistry((SlowTool(),)),
        tool_timeout_seconds=0.001,
    )

    result = await harness.run(
        user_message="查一下最新岗位",
        system_context="test",
        session_id="s-timeout",
        allowed_tool_names=frozenset({"slow_search"}),
    )

    assert result.reply == "搜索暂时超时，我先说明资料不足。"
    tool_message = gateway.requests[1].messages[-1]
    assert tool_message.role == "tool"
    assert '"status": "timeout"' in tool_message.content


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


@pytest.mark.asyncio
async def test_harness_serializes_turns_for_same_session() -> None:
    @dataclass
    class SlowGateway:
        active: int = 0
        max_active: int = 0

        async def generate(self, request: ModelRequest) -> ModelResponse:
            del request
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.02)
            self.active -= 1
            return ModelResponse(text="ok")

    gateway = SlowGateway()
    harness = CareerPilotHarness(gateway)

    await asyncio.gather(
        harness.run(user_message="a", system_context="s", session_id="same"),
        harness.run(user_message="b", system_context="s", session_id="same"),
    )

    assert gateway.max_active == 1


@pytest.mark.asyncio
async def test_harness_bounds_model_execution_time() -> None:
    class SlowGateway:
        async def generate(self, request: ModelRequest) -> ModelResponse:
            del request
            await asyncio.sleep(0.05)
            return ModelResponse(text="late")

    harness = CareerPilotHarness(SlowGateway(), model_timeout_seconds=0.001)

    with pytest.raises(TimeoutError):
        await harness.run(user_message="hello", system_context="s", session_id="s1")


def test_citation_audit_rejects_unknown_ids_and_detects_missing_citations() -> None:
    from careerpilot.harness.runtime import _audit_citations

    tool_message = HarnessMessage(
        role="tool",
        content=(
            '{"context_pack":{"evidence":['
            '{"citation_id":"S1"},{"citation_id":"S2"}]}}'
        ),
    )

    cited, warnings = _audit_citations("结论见 [S1] 和 [S9]。", (tool_message,))
    assert cited == ("S1",)
    assert warnings == ("invalid_citations:S9",)

    cited, warnings = _audit_citations("没有引用。", (tool_message,))
    assert cited == ()
    assert warnings == ("missing_citations",)


@pytest.mark.asyncio
async def test_harness_honors_durable_cancellation_before_model_call(tmp_path) -> None:
    store = SqliteAgentRunStore(tmp_path / "runs.db")
    await store.create(
        run_id="run-cancel",
        owner_id="owner-1",
        conversation_id="c1",
        session_id="s1",
        objective="cancel me",
    )
    await store.request_cancel("owner-1", "run-cancel")
    gateway = RecordingGateway([ModelResponse(text="must not run")])
    harness = CareerPilotHarness(gateway, run_store=store)

    try:
        with pytest.raises(RunCancellationRequested):
            await harness.run(
                user_message="hello",
                system_context="s",
                session_id="s1",
                run_id="run-cancel",
            )

        assert gateway.requests == []
        events = await store.list_events("owner-1", "run-cancel")
        assert [item.event_type for item in events or ()][-2:] == [
            "run.started",
            "run.cancelled",
        ]
    finally:
        store.close()
