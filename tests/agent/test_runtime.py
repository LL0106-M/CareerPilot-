from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from careerpilot.agent.runtime import CareerPilotResponder
from careerpilot.harness.events import HarnessEventType


class ToolCapableFakeChatModel(FakeMessagesListChatModel):
    bound_tool_names: list[str] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ToolCapableFakeChatModel":
        self.bound_tool_names = [item["function"]["name"] for item in tools]
        return self


@pytest.mark.asyncio
async def test_responder_runs_through_careerpilot_harness() -> None:
    model = ToolCapableFakeChatModel(
        responses=[AIMessage(content="我听见这次拒绝让你很难受，我们先不用急着找原因。")]
    )
    responder = CareerPilotResponder(model)

    reply = await responder.respond(
        "我被拒了，很难受",
        "先具体慰藉，当前模式为 listen。",
        "thread-1",
    )

    assert reply == "我听见这次拒绝让你很难受，我们先不用急着找原因。"


@pytest.mark.asyncio
async def test_responder_filters_tools_for_each_turn() -> None:
    @tool
    def search_career_knowledge(query: str) -> str:
        """Search the governed CareerPilot knowledge base."""
        return query

    model = ToolCapableFakeChatModel(responses=[AIMessage(content="先听你说。")])
    responder = CareerPilotResponder(model, tools=[search_career_knowledge])

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

    @tool
    def search_career_knowledge(query: str) -> str:
        """Search governed career evidence."""
        observed_queries.append(query)
        return "产品经理需要用户研究与跨团队协作"

    model = ToolCapableFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "search_career_knowledge",
                        "args": {"query": "产品经理能力"},
                    }
                ],
            ),
            AIMessage(content="可先验证用户研究和跨团队协作这两项能力。"),
        ]
    )
    responder = CareerPilotResponder(model, tools=[search_career_knowledge])

    reply = await responder.respond(
        "产品经理需要什么能力？",
        "使用可溯源证据回答。",
        "thread-tool",
        allowed_tool_names=frozenset({"search_career_knowledge"}),
    )

    assert observed_queries == ["产品经理能力"]
    assert reply == "可先验证用户研究和跨团队协作这两项能力。"


@pytest.mark.asyncio
async def test_runtime_tool_overrides_static_tool_with_same_name() -> None:
    calls: list[str] = []

    @tool
    def search_career_knowledge(query: str) -> str:
        """Static search."""
        calls.append("static")
        return query

    @tool("search_career_knowledge")
    def user_scoped_search(query: str) -> str:
        """User-scoped search."""
        calls.append("user")
        return query

    model = ToolCapableFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-private",
                        "name": "search_career_knowledge",
                        "args": {"query": "我的资料"},
                    }
                ],
            ),
            AIMessage(content="完成。"),
        ]
    )
    responder = CareerPilotResponder(model, tools=[search_career_knowledge])

    await responder.respond(
        "根据我的资料准备面试",
        "使用私有资料",
        "thread-private",
        allowed_tool_names=frozenset({"search_career_knowledge"}),
        runtime_tools=(user_scoped_search,),
    )

    assert calls == ["user"]
    assert model.bound_tool_names.count("search_career_knowledge") == 1


@pytest.mark.asyncio
async def test_responder_exposes_runtime_event_stream() -> None:
    model = ToolCapableFakeChatModel(responses=[AIMessage(content="我们先梳理。")])
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
