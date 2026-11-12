from collections.abc import AsyncIterator

import pytest

from careerpilot.agent.runtime import CareerPilotResponder
from careerpilot.harness.contracts import (
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ToolCall,
    ToolSchema,
)
from careerpilot.harness.events import HarnessEventType
from careerpilot.harness.tools import FunctionHarnessTool


def _tool(name: str, handler, description: str) -> FunctionHarnessTool:
    return FunctionHarnessTool(
        ToolSchema(
            name=name,
            description=description,
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        handler,
    )


class ScriptedModelGateway:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.bound_tool_names: list[str] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.bound_tool_names = [item.name for item in request.tools]
        return self.responses.pop(0)

    async def stream(
        self, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        response = await self.generate(request)
        if response.text:
            yield ModelStreamEvent(text_delta=response.text)
        yield ModelStreamEvent(response=response)


@pytest.mark.asyncio
async def test_responder_runs_through_careerpilot_harness() -> None:
    model = ScriptedModelGateway(
        responses=[ModelResponse(text="我听见这次拒绝让你很难受，我们先不用急着找原因。")]
    )
    responder = CareerPilotResponder(model)

    reply = await responder.respond(
        "我被拒了，很难受",
        "先具体慰藉，当前模式为 listen。",
        "thread-1",
    )

    assert reply.reply == "我听见这次拒绝让你很难受，我们先不用急着找原因。"
    assert reply.run_id


@pytest.mark.asyncio
async def test_responder_filters_tools_for_each_turn() -> None:
    def search_career_knowledge(query: str) -> str:
        return query
    search_tool = _tool(
        "search_career_knowledge",
        search_career_knowledge,
        "Search the governed CareerPilot knowledge base.",
    )

    model = ScriptedModelGateway(responses=[ModelResponse(text="先听你说。")])
    responder = CareerPilotResponder(model, tools=[search_tool])

    await responder.respond(
        "我现在只想说说",
        "当前模式 listen",
        "thread-listen",
        allowed_tool_names=frozenset(),
    )

    assert "search_career_knowledge" not in model.bound_tool_names


@pytest.mark.asyncio
async def test_responder_executes_tool_and_returns_second_model_response() -> None:
    observed_queries: list[str] = []

    def search_career_knowledge(query: str) -> str:
        observed_queries.append(query)
        return "产品经理需要用户研究与跨团队协作"
    search_tool = _tool(
        "search_career_knowledge",
        search_career_knowledge,
        "Search governed career evidence.",
    )

    model = ScriptedModelGateway(
        responses=[
            ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="call-1",
                        name="search_career_knowledge",
                        arguments={"query": "产品经理能力"},
                    ),
                ),
            ),
            ModelResponse(text="可先验证用户研究和跨团队协作这两项能力。"),
        ]
    )
    responder = CareerPilotResponder(model, tools=[search_tool])

    reply = await responder.respond(
        "产品经理需要什么能力？",
        "使用可溯源证据回答。",
        "thread-tool",
        allowed_tool_names=frozenset({"search_career_knowledge"}),
    )

    assert observed_queries == ["产品经理能力"]
    assert reply.reply == "可先验证用户研究和跨团队协作这两项能力。"


@pytest.mark.asyncio
async def test_runtime_rejects_duplicate_tool_names() -> None:
    calls: list[str] = []

    def search_career_knowledge(query: str) -> str:
        calls.append("static")
        return query
    static_tool = _tool(
        "search_career_knowledge", search_career_knowledge, "Static search."
    )

    def user_scoped_search(query: str) -> str:
        calls.append("user")
        return query
    runtime_tool = _tool(
        "search_career_knowledge", user_scoped_search, "User-scoped search."
    )

    model = ScriptedModelGateway(
        responses=[
            ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="call-private",
                        name="search_career_knowledge",
                        arguments={"query": "我的资料"},
                    ),
                ),
            ),
            ModelResponse(text="完成。"),
        ]
    )
    responder = CareerPilotResponder(model, tools=[static_tool])

    with pytest.raises(ValueError, match="Duplicate tool name"):
        await responder.respond(
            "根据我的资料准备面试",
            "使用私有资料",
            "thread-private",
            allowed_tool_names=frozenset({"search_career_knowledge"}),
            runtime_tools=(runtime_tool,),
        )

    assert calls == []


@pytest.mark.asyncio
async def test_responder_exposes_runtime_event_stream() -> None:
    model = ScriptedModelGateway(responses=[ModelResponse(text="我们先梳理。")])
    responder = CareerPilotResponder(model)

    events = [
        event
        async for event in responder.stream(
            "我有点乱",
            "当前模式 organize",
            "thread-stream",
            run_id="run-stream",
        )
    ]

    assert events[0].type is HarnessEventType.RUN_STARTED
    assert events[-1].type is HarnessEventType.RUN_COMPLETED
    assert events[-1].data["reply"] == "我们先梳理。"
